from django.conf import settings
from django.db import models

class AllowedExtension(models.Model):
    """Allowlist of file extensions (without dot)."""
    ext = models.CharField(max_length=32, unique=True)
    description = models.CharField(max_length=128, blank=True)
    enabled = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f".{self.ext}"

class Asset(models.Model):
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="assets")
    bucket = models.CharField(max_length=64, db_index=True)
    original_name = models.CharField(max_length=255)
    rel_path = models.CharField(max_length=512)  # inside user folder
    size = models.BigIntegerField()
    mime = models.CharField(max_length=128, default='application/octet-stream')
    is_public = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        unique_together = ("owner", "bucket", "rel_path", "original_name")

    def __str__(self):
        ns = getattr(self.owner, 'name_spase', self.owner.username)
        return f"{ns}/{self.bucket}/{self.rel_path}"

    @property
    def public_url(self) -> str:
        ns = getattr(self.owner, 'name_spase', self.owner.username)
        base = f"/cdn/{ns}/{self.bucket}"
        return f"{base}/{self.rel_path}/{self.original_name}" if self.rel_path else f"{base}/{self.original_name}"