from __future__ import annotations
import io
from typing import List
from django.conf import settings
from django.db.models import Q
from django.http import JsonResponse, HttpResponseBadRequest, HttpResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt

from .models import Asset, AllowedExtension
from .utils import (
    compute_sha256,
    suggest_hashed_name,
    guess_mime,
    ensure_cdn_path,
    extract_extension,
)

# ----------
# Web UI
# ----------

def dashboard(request):
    """Simple modern dashboard: upload form + recent assets."""
    return render(request, 'core/dashboard.html')


def api_assets(request):
    """List assets for the dashboard table (small, paginated in UI)."""
    q = request.GET.get('q')
    qs = Asset.objects.all()
    if q:
        qs = qs.filter(
            Q(original_name__icontains=q) |
            Q(hashed_name__icontains=q) |
            Q(bucket__icontains=q)
        )
    data = [
        {
            'bucket': a.bucket,
            'original_name': a.original_name,
            'hashed_name': a.hashed_name,
            'sha256': a.content_sha256,
            'size': a.size,
            'mime': a.mime,
            'created_at': a.created_at.isoformat(),
            'url': f"/cdn/{a.bucket}/{a.content_sha256[:2]}/{a.content_sha256}/{a.hashed_name}",
        }
        for a in qs[:200]
    ]
    return JsonResponse({'ok': True, 'items': data})

@LOGIN_REQUIRED
def api_allowed_extensions(request):
    exts = AllowedExtension.objects.filter(enabled=True).order_by('ext')
    return JsonResponse({'ok': True, 'items': [f".{e.ext}" for e in exts]})

# ----------
# Upload API (control plane)
# ----------

@csrf_exempt
def api_upload(request):
    """POST /api/upload?bucket=assets
    Multipart form key: file

    Security controls:
    - Enforce max size (settings.MAX_UPLOAD_SIZE)
    - Allowlist by extension from DB (AllowedExtension.enabled)
    - Content hashing and deterministic storage path
    - Basic MIME sniffing (optional python‑magic)
    """
    if request.method != 'POST' or 'file' not in request.FILES:
        return HttpResponseBadRequest('file required')

    bucket = (request.GET.get('bucket') or 'assets').strip()
    f = request.FILES['file']

    # Size cap (defense against abuse)
    if f.size > settings.MAX_UPLOAD_SIZE:
        return JsonResponse({'ok': False, 'error': 'file too large'}, status=413)

    # Extension allowlist
    ext = extract_extension(f.name)
    is_allowed = AllowedExtension.objects.filter(ext=ext, enabled=True).exists()
    if not is_allowed:
        return JsonResponse({'ok': False, 'error': f'extension .{ext} not allowed'}, status=415)

    # Peek first bytes for MIME probing if available
    head = f.read(min(8192, f.size))
    f.seek(0)
    mime = guess_mime(f.name, head)

    # Compute content hash
    sha256_hex = compute_sha256(f)
    hashed_name = suggest_hashed_name(f.name, sha256_hex)

    # Target path (dedup by content hash)
    path = ensure_cdn_path(bucket, sha256_hex, hashed_name)

    if not path.exists():
        # Stream to disk (avoid keeping entire file in memory)
        with path.open('wb') as dst:
            for chunk in f.chunks():
                dst.write(chunk)

    asset, _ = Asset.objects.get_or_create(
        bucket=bucket,
        content_sha256=sha256_hex,
        defaults=dict(
            original_name=f.name,
            hashed_name=hashed_name,
            size=path.stat().st_size,
            mime=mime,
            is_public=True,
        ),
    )

    public_url = f"/cdn/{bucket}/{sha256_hex[:2]}/{sha256_hex}/{asset.hashed_name}"
    return JsonResponse({
        'ok': True,
        'bucket': bucket,
        'name': asset.hashed_name,
        'sha256': sha256_hex,
        'size': asset.size,
        'mime': asset.mime,
        'url': public_url,
    })