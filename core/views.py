from __future__ import annotations
import io
import json
import os
import zipfile
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponseBadRequest, StreamingHttpResponse, HttpResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST
from django.db.models import Q

from .models import Asset, AllowedExtension
from .utils import (
    safe_filename,
    extract_extension,
    sanitize_rel_path,
    build_storage_path,
    ensure_unique,
    guess_mime, fs_base, safe_folder_name,
)

# ---------- UI ----------

@login_required
def dashboard(request):
    """Dashboard with upload form + folder browser."""
    return render(request, 'core/dashboard.html')

# ---------- APIs ----------

@login_required
@require_GET
def api_allowed_extensions(request):
    exts = AllowedExtension.objects.filter(enabled=True).order_by('ext')
    return JsonResponse({'ok': True, 'items': [f".{e.ext}" for e in exts]})

@login_required
@require_GET
def api_assets(request):
    """Flat listing (search) limited to current user."""
    q = request.GET.get('q')
    bucket = request.GET.get('bucket')
    rel = request.GET.get('rel_path')

    qs = Asset.objects.filter(owner=request.user)
    if bucket:
        qs = qs.filter(bucket=bucket)
    if rel:
        qs = qs.filter(rel_path=rel)
    if q:
        qs = qs.filter(
            Q(original_name__icontains=q) |
            Q(bucket__icontains=q) |
            Q(rel_path__icontains=q)
        )

    data = [{
        'bucket': a.bucket,
        'rel_path': a.rel_path,
        'original_name': a.original_name,
        'size': a.size,
        'mime': a.mime,
        'created_at': a.created_at.isoformat(),
        'url': a.public_url,
    } for a in qs[:200]]

    return JsonResponse({'ok': True, 'items': data})



@login_required
@csrf_exempt
@require_POST
def api_upload(request):
    """Multi‑upload under the authenticated user's namespace.
    POST /api/upload?bucket=assets&rel_path=path/inside
    multipart: files=<multiple files> OR file=<single>
    Security: allowlist by extension, size cap, sanitized rel_path, no overwrite.
    """
    bucket = (request.GET.get('bucket') or 'assets').strip()
    rel_raw = request.GET.get('rel_path') or ''
    try:
        rel_path = sanitize_rel_path(rel_raw)
    except ValueError as e:
        return JsonResponse({'ok': False, 'error': str(e)}, status=400)

    files = request.FILES.getlist('files') or ([request.FILES['file']] if 'file' in request.FILES else [])
    if not files:
        return HttpResponseBadRequest('files required')

    results = []
    for f in files:
        if f.size > settings.MAX_UPLOAD_SIZE:
            results.append({'ok': False, 'name': f.name, 'error': 'file too large'})
            continue
        safe_name = safe_filename(f.name)
        ext = extract_extension(safe_name)
        if not AllowedExtension.objects.filter(ext=ext, enabled=True).exists():
            results.append({'ok': False, 'name': safe_name, 'error': f'extension .{ext} not allowed'})
            continue

        head = f.read(min(8192, f.size)); f.seek(0)
        mime = guess_mime(safe_name, head)

        path = build_storage_path(request.user, bucket, rel_path, safe_name)
        path = ensure_unique(path)

        tmp = path.with_suffix(path.suffix + '.part')
        with tmp.open('wb') as dst:
            for chunk in f.chunks():
                dst.write(chunk)
        os.replace(tmp, path)

        a = Asset.objects.create(
            owner=request.user,
            bucket=bucket,
            original_name=path.name,
            rel_path=rel_path,
            size=path.stat().st_size,
            mime=mime,
            is_public=True,
        )
        results.append({'ok': True, 'url': a.public_url, 'name': a.original_name})

    return JsonResponse({'ok': all(r.get('ok') for r in results), 'items': results})

@login_required
@require_POST
@csrf_exempt
def api_zip(request):
    """Download a ZIP of selected files owned by the current user.
    Body JSON: {"items": [{"bucket":"assets","rel_path":"path","name":"file.ext"}, ...]}
    """
    try:
        data = json.loads(request.body.decode('utf-8'))
    except Exception:
        return JsonResponse({'ok': False, 'error': 'invalid json'}, status=400)

    items = data.get('items') or []
    if not items:
        return JsonResponse({'ok': False, 'error': 'no items'}, status=400)

    def stream():
        bio = io.BytesIO()
        with zipfile.ZipFile(bio, 'w', compression=zipfile.ZIP_DEFLATED) as zf:
            for it in items:
                bucket = (it.get('bucket') or 'assets').strip()
                rel = sanitize_rel_path(it.get('rel_path') or '')
                name = safe_filename(it.get('name') or '')
                try:
                    a = Asset.objects.get(owner=request.user, bucket=bucket, rel_path=rel, original_name=name)
                except Asset.DoesNotExist:
                    continue
                p = build_storage_path(request.user, a.bucket, a.rel_path, a.original_name)
                if not p.exists():
                    continue
                arc = f"{a.rel_path+'/'+a.original_name if a.rel_path else a.original_name}"
                zf.write(p, arcname=arc)
        bio.seek(0)
        yield from bio

    resp = StreamingHttpResponse(stream(), content_type='application/zip')
    resp['Content-Disposition'] = 'attachment; filename="download.zip"'
    return resp

@login_required
@require_GET
@csrf_exempt

def api_file_private(request):
    """Private file gate using Nginx X-Accel-Redirect. Only owner can access."""
    bucket = (request.GET.get('bucket') or 'assets').strip()
    rel = sanitize_rel_path(request.GET.get('rel_path') or '')
    name = safe_filename(request.GET.get('name') or '')
    try:
        a = Asset.objects.get(owner=request.user, bucket=bucket, rel_path=rel, original_name=name)
    except Asset.DoesNotExist:
        return JsonResponse({'ok': False, 'error': 'not found'}, status=404)

    ns = getattr(request.user, 'name_spase', request.user.username)
    internal = f"/_protected/{ns}/{a.bucket}/{a.rel_path}/{a.original_name}" if a.rel_path else f"/_protected/{ns}/{a.bucket}/{a.original_name}"
    resp = HttpResponse()
    resp['X-Accel-Redirect'] = internal
    resp['Content-Type'] = a.mime
    return resp




@login_required
@require_GET
@csrf_exempt

def api_browse(request):
    """
    List folders/files one level under rel_path for current user.
    Now also lists empty folders that exist on disk.
    """
    bucket = (request.GET.get('bucket') or 'assets').strip()
    rel = sanitize_rel_path(request.GET.get('rel_path') or '')

    qs = Asset.objects.filter(owner=request.user, bucket=bucket)

    # Folders from DB (derived from rel_path deeper levels)
    prefix = f"{rel}/" if rel else ''
    child_candidates = qs.exclude(rel_path='').values_list('rel_path', flat=True)
    folders_db = set()
    for p in child_candidates:
        if not p.startswith(prefix):
            continue
        rest = p[len(prefix):]
        if not rest:
            continue
        # only count as folder if there's deeper level
        if '/' in rest:
            first = rest.split('/', 1)[0]
            folders_db.add(first)

    # Folders from filesystem (empty-folders support)
    base = fs_base(request.user, bucket, rel)
    folders_fs = set()
    try:
        for entry in base.iterdir():
            if entry.is_dir():
                folders_fs.add(entry.name)
    except FileNotFoundError:
        pass

    folders = sorted(folders_db | folders_fs)

    # Files directly in rel (from DB, fast)
    files_qs = qs.filter(rel_path=rel)
    files = [{
        'name': a.original_name,
        'size': a.size,
        'mime': a.mime,
        'url': a.public_url,
        'created_at': a.created_at.isoformat(),
    } for a in files_qs]

    return JsonResponse({'ok': True, 'path': rel, 'folders': folders, 'files': files})


# ---------- New: mkdir ----------

@login_required
@require_POST
@csrf_exempt

def api_mkdir(request):
    """
    POST /api/mkdir
    JSON: { "bucket":"assets", "rel_path":"current/path", "name":"NewFolder" }
    Creates folder at <rel_path>/<name>
    """
    try:
        data = json.loads(request.body.decode('utf-8'))
    except Exception:
        return JsonResponse({'ok': False, 'error': 'invalid json'}, status=400)

    bucket = (data.get('bucket') or 'assets').strip()
    rel = sanitize_rel_path(data.get('rel_path') or '')
    name = safe_folder_name(data.get('name') or '')

    target = fs_base(request.user, bucket, rel) / name
    if target.exists():
        return JsonResponse({'ok': False, 'error': 'folder exists'}, status=409)

    target.mkdir(parents=True, exist_ok=False)
    return JsonResponse({'ok': True})


# ---------- New: rename / move file ----------

@login_required
@require_POST
@csrf_exempt

def api_rename(request):
    """
    POST /api/rename
    JSON: {
      "bucket":"assets",
      "old_rel_path":"a/b",
      "old_name":"file.css",
      "new_rel_path":"a/c",  # optional; default old_rel_path
      "new_name":"file2.css" # optional; default old_name
    }
    """
    try:
        data = json.loads(request.body.decode('utf-8'))
    except Exception:
        return JsonResponse({'ok': False, 'error': 'invalid json'}, status=400)

    bucket = (data.get('bucket') or 'assets').strip()

    old_rel = sanitize_rel_path(data.get('old_rel_path') or '')
    new_rel = sanitize_rel_path(data.get('new_rel_path') or old_rel)

    old_name = safe_filename(data.get('old_name') or '')
    new_name = safe_filename(data.get('new_name') or old_name)

    # Ensure asset exists and is owned by user
    try:
        a = Asset.objects.get(owner=request.user, bucket=bucket, rel_path=old_rel, original_name=old_name)
    except Asset.DoesNotExist:
        return JsonResponse({'ok': False, 'error': 'not found'}, status=404)

    old_p = build_storage_path(request.user, bucket, old_rel, old_name)
    if not old_p.exists():
        return JsonResponse({'ok': False, 'error': 'file missing on disk'}, status=404)

    # Destination
    new_p = build_storage_path(request.user, bucket, new_rel, new_name)
    if new_p.exists():
        return JsonResponse({'ok': False, 'error': 'target exists'}, status=409)

    new_p.parent.mkdir(parents=True, exist_ok=True)
    os.replace(old_p, new_p)

    # Update DB
    a.rel_path = new_rel
    a.original_name = new_name
    a.save(update_fields=['rel_path', 'original_name'])

    return JsonResponse({'ok': True})


# ---------- New: delete file ----------

@login_required
@require_POST
@csrf_exempt

def api_delete(request):
    """
    POST /api/delete
    JSON: { "bucket":"assets", "rel_path":"a/b", "name":"file.css" }
    Deletes file from disk and DB.
    """
    try:
        data = json.loads(request.body.decode('utf-8'))
    except Exception:
        return JsonResponse({'ok': False, 'error': 'invalid json'}, status=400)

    bucket = (data.get('bucket') or 'assets').strip()
    rel = sanitize_rel_path(data.get('rel_path') or '')
    name = safe_filename(data.get('name') or '')

    try:
        a = Asset.objects.get(owner=request.user, bucket=bucket, rel_path=rel, original_name=name)
    except Asset.DoesNotExist:
        return JsonResponse({'ok': False, 'error': 'not found'}, status=404)

    p = build_storage_path(request.user, bucket, rel, name)
    try:
        if p.exists():
            p.unlink()
    except Exception:
        # If deletion fails on FS, do not delete DB to avoid ghost references
        return JsonResponse({'ok': False, 'error': 'fs delete failed'}, status=500)

    a.delete()
    return JsonResponse({'ok': True})
