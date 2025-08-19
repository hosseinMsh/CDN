import os, mimetypes, re
from pathlib import Path
from django.conf import settings
from django.db.models import F
from .models import Space

SAFE_NAME_RE = re.compile(r"[^A-Za-z0-9._-]+")

def safe_filename(name: str) -> str:
    """Make filename filesystem/URL safe; strip directories and replace invalid chars."""
    name = name.replace("\\", "/").split("/")[-1]
    return (SAFE_NAME_RE.sub('-', name).strip('.') or 'file')[:255]

def extract_extension(filename: str) -> str:
    """Return last extension without dot, lowercased."""
    return os.path.splitext(filename)[1].lower().lstrip('.')

def sanitize_rel_path(rel_path: str) -> str:
    """Normalize optional subpath (inside user namespace). Reject traversal/invalid chars."""
    if not rel_path: return ''
    rel_path = rel_path.strip().strip('/')
    if '..' in rel_path or rel_path.startswith('/'): raise ValueError('invalid rel_path')
    parts = [p for p in rel_path.replace('\\','/').split('/') if p and p!='.']
    for p in parts:
        if SAFE_NAME_RE.search(p): raise ValueError('invalid characters in rel_path')
    return '/'.join(parts)

def safe_folder_name(name: str) -> str:
    """Filesystem path: CDN_ROOT/<name_spase>/<rel_path>/filename"""
    name = (name or '').strip().strip('/')
    if not name or '..' in name or '/' in name: raise ValueError('invalid folder name')
    if SAFE_NAME_RE.search(name): raise ValueError('invalid folder name')
    return name[:64]

def ns_base(space: Space) -> Path:
    """Base directory for a user's space:
       CDN_ROOT/<name_spase>/<space.slug>/"""
    root: Path = settings.CDN_ROOT
    p = root / space.owner.name_spase / space.slug
    p.mkdir(parents=True, exist_ok=True)
    return p

def fs_base(space: Space, rel_path: str = '') -> Path:
    base = ns_base(space)
    if rel_path:
        base = base / rel_path
    base.mkdir(parents=True, exist_ok=True)
    return base

def build_storage_path(space: Space, rel_path: str, filename: str) -> Path:
    p = fs_base(space, rel_path) / filename
    p.parent.mkdir(parents=True, exist_ok=True)
    return p

def ensure_unique(p: Path) -> Path:
    """If file exists, append (n) to the name to avoid overwriting."""
    if not p.exists(): return p
    base, ext = p.stem, p.suffix
    i = 1
    while True:
        cand = p.with_name(f"{base} ({i}){ext}")
        if not cand.exists(): return cand
        i += 1

def guess_mime(name: str, sample_bytes: bytes | None = None) -> str:
    """Best‑effort MIME detection using python‑magic if available; fallback to mimetypes."""
    if getattr(settings, 'MAGIC_AVAILABLE', False) and sample_bytes:
        try:
            import magic  # type: ignore
            m = magic.Magic(mime=True)
            return m.from_buffer(sample_bytes)
        except Exception:
            pass
    return mimetypes.guess_type(name)[0] or 'application/octet-stream'
