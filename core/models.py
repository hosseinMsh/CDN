from django.db import models

class AllowedExtension(models.Model):
    """Allowlist of file extensions that are permitted to be uploaded.
    Extensions are stored without leading dot (e.g., 'png', 'css').
    """
    ext = models.CharField(max_length=32, unique=True)
    description = models.CharField(max_length=128, blank=True)
    enabled = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f".{self.ext}"

class Asset(models.Model):
    """Metadata about a stored object. Content is addressed by sha256 and
    served by Nginx from disk; Django is used for control plane only.
    """
    bucket = models.CharField(max_length=64, db_index=True)
    original_name = models.CharField(max_length=255)
    hashed_name = models.CharField(max_length=255, db_index=True)
    content_sha256 = models.CharField(max_length=64, db_index=True)
    size = models.BigIntegerField()
    mime = models.CharField(max_length=128, default='application/octet-stream')
    is_public = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["bucket", "hashed_name"]),
            models.Index(fields=["bucket", "content_sha256"]),
        ]
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.bucket}/{self.hashed_name}"