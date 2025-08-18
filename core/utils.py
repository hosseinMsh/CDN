import os
import mimetypes
import re
from pathlib import Path
from django.conf import settings

SAFE_NAME_RE = re.compile(r"[^A-Za-z0-9._-]+")

# ---------- Sanitation ----------

def safe_filename(name: str) -> str:
    """Make filename filesystem/URL safe; strip directories and replace invalid chars."""
    name = name.replace("\\", "/").split("/")[-1]
    return SAFE_NAME_RE.sub('-', name).strip('.') or 'file'


def extract_extension(filename: str) -> str:
    """Return last extension without dot, lowercased."""
    return os.path.splitext(filename)[1].lower().lstrip('.')


def sanitize_rel_path(rel_path: str) -> str:
    """Normalize optional subpath (inside user namespace). Reject traversal/invalid chars."""
    if not rel_path:
        return ''
    rel_path = rel_path.strip().strip('/')
    if '..' in rel_path or rel_path.startswith('/'):
        raise ValueError('invalid rel_path')
    parts = [p for p in rel_path.replace('\\','/').split('/') if p and p != '.']
    for p in parts:
        if SAFE_NAME_RE.search(p):
            raise ValueError('invalid characters in rel_path')
    return '/'.join(parts)

# ---------- Storage paths ----------

def build_storage_path(owner, bucket: str, rel_path: str, filename: str) -> Path:
    """Filesystem path: CDN_ROOT/<name_spase>/<bucket>/<rel_path>/filename"""
    ns = getattr(owner, 'name_spase', owner.username)
    root: Path = settings.CDN_ROOT
    base = root / ns / bucket
    if rel_path:
        base = base / rel_path
    p = base / filename
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def ensure_unique(p: Path) -> Path:
    """If file exists, append (n) to the name to avoid overwriting."""
    if not p.exists():
        return p
    base, ext = p.stem, p.suffix
    i = 1
    while True:
        cand = p.with_name(f"{base} ({i}){ext}")
        if not cand.exists():
            return cand
        i += 1

# ---------- MIME ----------

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