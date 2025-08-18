import os
import hashlib
import mimetypes
from pathlib import Path
from django.conf import settings

# ----------
# Helpers
# ----------

def compute_sha256(fileobj) -> str:
    """Compute sha256 by streaming the file; rewind to start afterward."""
    h = hashlib.sha256()
    for chunk in iter(lambda: fileobj.read(1024 * 1024), b""):
        h.update(chunk)
    fileobj.seek(0)
    return h.hexdigest()


def suggest_hashed_name(original_name: str, sha256_hex: str) -> str:
    """Return a versioned filename: base.<first7hash>.ext"""
    base, ext = os.path.splitext(original_name)
    short = sha256_hex[:7]
    return f"{base}.{short}{ext}"


def guess_mime(name: str, sample_bytes: bytes | None = None) -> str:
    """Best‑effort MIME detection.
    If python‑magic is available and sample is provided, use it; otherwise use mimetypes.
    """
    if getattr(settings, 'MAGIC_AVAILABLE', False) and sample_bytes:
        try:
            import magic  # type: ignore
            m = magic.Magic(mime=True)
            return m.from_buffer(sample_bytes)
        except Exception:
            pass
    return mimetypes.guess_type(name)[0] or "application/octet-stream"


def ensure_cdn_path(bucket: str, sha256_hex: str, hashed_name: str) -> Path:
    """Build the full path where the object will reside."""
    root: Path = settings.CDN_ROOT
    p = root / bucket / sha256_hex[:2] / sha256_hex / hashed_name
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def extract_extension(filename: str) -> str:
    """Return the last extension without dot, lowercased (e.g., 'png').
    Note: For multi‑part like .tar.gz this returns 'gz'. Improve as needed.
    """
    return os.path.splitext(filename)[1].lower().lstrip('.')