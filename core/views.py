from __future__ import annotations
import io, os, json, zipfile
from django.db import transaction
from django.db.models import Q, F
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponseBadRequest, StreamingHttpResponse, HttpResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from .models import AllowedExtension, Space, Asset
from .utils import (
    safe_filename, extract_extension, sanitize_rel_path, safe_folder_name,
    build_storage_path, ensure_unique, guess_mime, fs_base
)

# ---------- helpers ----------

def get_current_space(request) -> Space | None:
    sid = request.session.get("space_id")
    if not request.user.is_authenticated:
        return None
    qs = Space.objects.filter(owner=request.user)
    if sid:
        sp = qs.filter(id=sid).first()
        if sp: return sp
    # lazy bootstrap default
    sp = qs.filter(is_default=True).first()
    if sp:
        request.session["space_id"] = sp.id
        return sp
    # create a default if none
    with transaction.atomic():
        sp = Space.objects.create(owner=request.user, name="Default", slug="default", is_default=True)
    request.session["space_id"] = sp.id
    return sp

@login_required
def dashboard(request):
    """Dashboard with upload form + folder browser."""
    return render(request, 'core/dashboard.html', {'space': get_current_space(request)})

# ---------- spaces: list + switch ----------

@login_required
@require_GET
@csrf_exempt
def api_spaces(request):
    spaces = Space.objects.filter(owner=request.user).order_by('-is_default','name')
    space = get_current_space(request)
    items = [{
        'id': s.id, 'name': s.name, 'slug': s.slug, 'is_default': s.is_default,
        'max_bytes': int(s.max_bytes), 'max_files': int(s.max_files),
        'used_bytes': int(s.used_bytes), 'file_count': int(s.file_count),
        'current': (space and s.id == space.id),
    } for s in spaces]
    return JsonResponse({'ok': True, 'items': items})

@login_required
@require_POST
@csrf_exempt
def api_space_set(request):
    data = json.loads(request.body.decode('utf-8'))
    sid = data.get('space_id')
    s = Space.objects.filter(owner=request.user, id=sid).first()
    if not s: return JsonResponse({'ok': False, 'error': 'space not found'}, status=404)
    request.session['space_id'] = s.id
    return JsonResponse({'ok': True})

# ---------- browse/list ----------

@login_required
@require_GET
@csrf_exempt
def api_browse(request):
    space = get_current_space(request)
    if not space: return JsonResponse({'ok': False, 'error': 'no space'}, status=400)
    rel = sanitize_rel_path(request.GET.get('rel_path') or '')

    qs = Asset.objects.filter(space=space)

    # Folders (DB + FS to include empty ones)
    prefix = f"{rel}/" if rel else ''
    folders_db = set()
    for p in qs.exclude(rel_path='').values_list('rel_path', flat=True):
        if not p.startswith(prefix): continue
        rest = p[len(prefix):]
        if not rest: continue
        if '/' in rest:
            folders_db.add(rest.split('/',1)[0])

    folders_fs = set()
    try:
        for entry in fs_base(space, rel).iterdir():
            if entry.is_dir(): folders_fs.add(entry.name)
    except FileNotFoundError:
        pass

    folders = sorted(folders_db | folders_fs)

    files = [{
        'name': a.original_name, 'size': a.size, 'mime': a.mime,
        'url': a.public_url, 'created_at': a.created_at.isoformat(),
    } for a in qs.filter(rel_path=rel)]

    return JsonResponse({'ok': True, 'path': rel, 'folders': folders, 'files': files})

@login_required
@require_GET
@csrf_exempt
def api_assets(request):
    space = get_current_space(request)
    if not space: return JsonResponse({'ok': False, 'error': 'no space'}, status=400)
    q = request.GET.get('q')
    qs = Asset.objects.filter(space=space)
    if q:
        qs = qs.filter(Q(original_name__icontains=q) | Q(rel_path__icontains=q) | Q(mime__icontains=q))
    items = [{'original_name': a.original_name, 'size': a.size, 'mime': a.mime, 'url': a.public_url} for a in qs[:300]]
    return JsonResponse({'ok': True, 'items': items})

# ---------- allowed extensions ----------

@login_required
@require_GET
@csrf_exempt
def api_allowed_extensions(request):
    exts = AllowedExtension.objects.filter(enabled=True).order_by('ext')
    return JsonResponse({'ok': True, 'items': [f".{e.ext}" for e in exts]})

# ---------- mkdir / rename / delete (single) ----------

@login_required
@require_POST
@csrf_exempt
def api_mkdir(request):
    space = get_current_space(request)
    if not space: return JsonResponse({'ok': False, 'error': 'no space'}, status=400)
    data = json.loads(request.body.decode('utf-8'))
    rel = sanitize_rel_path(data.get('rel_path') or '')
    name = safe_folder_name(data.get('name') or '')
    target = fs_base(space, rel) / name
    if target.exists(): return JsonResponse({'ok': False, 'error': 'folder exists'}, status=409)
    target.mkdir(parents=True, exist_ok=False)
    return JsonResponse({'ok': True})

@login_required
@require_POST
@csrf_exempt
def api_rename(request):
    space = get_current_space(request)
    if not space: return JsonResponse({'ok': False, 'error': 'no space'}, status=400)
    data = json.loads(request.body.decode('utf-8'))
    old_rel = sanitize_rel_path(data.get('old_rel_path') or '')
    new_rel = sanitize_rel_path(data.get('new_rel_path') or old_rel)
    old_name = safe_filename(data.get('old_name') or '')
    new_name = safe_filename(data.get('new_name') or old_name)

    try:
        a = Asset.objects.get(space=space, rel_path=old_rel, original_name=old_name)
    except Asset.DoesNotExist:
        return JsonResponse({'ok': False, 'error': 'not found'}, status=404)

    old_p = build_storage_path(space, old_rel, old_name)
    if not old_p.exists(): return JsonResponse({'ok': False, 'error': 'missing on disk'}, status=404)
    new_p = build_storage_path(space, new_rel, new_name)
    if new_p.exists(): return JsonResponse({'ok': False, 'error': 'target exists'}, status=409)
    new_p.parent.mkdir(parents=True, exist_ok=True)
    os.replace(old_p, new_p)
    a.rel_path, a.original_name = new_rel, new_name
    a.save(update_fields=['rel_path', 'original_name'])
    return JsonResponse({'ok': True})

@login_required
@require_POST
@csrf_exempt
def api_delete(request):
    space = get_current_space(request)
    if not space: return JsonResponse({'ok': False, 'error': 'no space'}, status=400)
    data = json.loads(request.body.decode('utf-8'))
    rel = sanitize_rel_path(data.get('rel_path') or '')
    name = safe_filename(data.get('name') or '')
    try:
        a = Asset.objects.get(space=space, rel_path=rel, original_name=name)
    except Asset.DoesNotExist:
        return JsonResponse({'ok': False, 'error': 'not found'}, status=404)

    p = build_storage_path(space, rel, name)
    try:
        if p.exists(): p.unlink()
    except Exception:
        return JsonResponse({'ok': False, 'error': 'fs delete failed'}, status=500)
    # accounting
    Space.objects.filter(id=space.id).update(
        used_bytes=F('used_bytes') - a.size,
        file_count=F('file_count') - 1
    )
    a.delete()
    return JsonResponse({'ok': True})

# ---------- batch delete ----------

@login_required
@require_POST
@csrf_exempt
def api_delete_batch(request):
    space = get_current_space(request)
    if not space: return JsonResponse({'ok': False, 'error': 'no space'}, status=400)
    data = json.loads(request.body.decode('utf-8'))
    items = data.get('items') or []  # [{rel_path, name}]
    ok = 0; err = 0
    total_released = 0
    for it in items:
        rel = sanitize_rel_path(it.get('rel_path') or '')
        name = safe_filename(it.get('name') or '')
        try:
            a = Asset.objects.get(space=space, rel_path=rel, original_name=name)
        except Asset.DoesNotExist:
            err += 1; continue
        p = build_storage_path(space, rel, name)
        try:
            if p.exists(): p.unlink()
            total_released += a.size
            a.delete()
            ok += 1
        except Exception:
            err += 1
    if ok:
        Space.objects.filter(id=space.id).update(
            used_bytes=F('used_bytes') - total_released,
            file_count=F('file_count') - ok
        )
    return JsonResponse({'ok': True, 'deleted': ok, 'failed': err})

# ---------- upload with quotas ----------

@login_required
@csrf_exempt
@require_POST
def api_upload(request):
    """
    POST /api/upload?bucket=assets&rel_path=a/b
    multipart: file=@...
    Enforces per-space quotas: max_bytes, max_files
    """
    space = get_current_space(request)
    if not space: return JsonResponse({'ok': False, 'error': 'no space'}, status=400)
    rel = sanitize_rel_path(request.GET.get('rel_path') or '')
    if 'file' not in request.FILES: return HttpResponseBadRequest('file required')
    f = request.FILES['file']

    # extension allowlist
    ext = extract_extension(f.name)
    if not AllowedExtension.objects.filter(ext=ext, enabled=True).exists():
        return JsonResponse({'ok': False, 'error': f'extension .{ext} not allowed'}, status=415)

    # quotas: check against current totals (race-safe enough for single-node)
    if space.file_count + 1 > space.max_files:
        return JsonResponse({'ok': False, 'error': 'file limit exceeded'}, status=403)
    if space.used_bytes + f.size > space.max_bytes:
        return JsonResponse({'ok': False, 'error': 'space out of quota'}, status=403)

    safe_name = safe_filename(f.name)
    head = f.read(min(8192, f.size)); f.seek(0)
    mime = guess_mime(safe_name, head)

    path = build_storage_path(space, rel, safe_name)
    path = ensure_unique(path)

    tmp = path.with_suffix(path.suffix + ".part")
    with tmp.open('wb') as dst:
        for chunk in f.chunks():
            dst.write(chunk)
    os.replace(tmp, path)
    size = path.stat().st_size

    # create asset + update accounting atomically
    with transaction.atomic():
        a = Asset.objects.create(
            space=space, rel_path=rel, original_name=path.name,
            size=size, mime=mime, is_public=True
        )
        Space.objects.filter(id=space.id).update(
            used_bytes=F('used_bytes') + size,
            file_count=F('file_count') + 1
        )

    return JsonResponse({'ok': True, 'url': a.public_url, 'name': a.original_name, 'size': a.size, 'mime': a.mime})

# ---------- zip (selected) ----------

@login_required
@require_POST
@csrf_exempt
def api_zip(request):
    space = get_current_space(request)
    if not space: return JsonResponse({'ok': False, 'error': 'no space'}, status=400)
    data = json.loads(request.body.decode('utf-8'))
    items = data.get('items') or []  # [{rel_path, name}]
    if not items: return JsonResponse({'ok': False, 'error': 'no items'}, status=400)

    def stream():
        bio = io.BytesIO()
        with zipfile.ZipFile(bio, 'w', compression=zipfile.ZIP_DEFLATED) as z:
            for it in items:
                rel = sanitize_rel_path(it.get('rel_path') or '')
                name = safe_filename(it.get('name') or '')
                try:
                    a = Asset.objects.get(space=space, rel_path=rel, original_name=name)
                except Asset.DoesNotExist:
                    continue
                p = build_storage_path(space, rel, name)
                if p.exists():
                    arcname = f"{rel+'/'+name if rel else name}"
                    z.write(p, arcname=arcname)
        bio.seek(0)
        yield from bio

    resp = StreamingHttpResponse(stream(), content_type='application/zip')
    resp['Content-Disposition'] = 'attachment; filename="download.zip"'
    return resp
