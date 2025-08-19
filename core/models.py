from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()

class AllowedExtension(models.Model):
    """Allowlist of file extensions (without dot)."""
    ext = models.CharField(max_length=32, unique=True)
    description = models.CharField(max_length=128, blank=True)
    enabled = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    def __str__(self): return f".{self.ext}"

class Space(models.Model):
    """Per-user workspace. Only admins can create additional spaces in Admin."""
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name="spaces")
    name = models.CharField(max_length=64)          # display name
    slug = models.SlugField(max_length=64)          # used in paths/URLs
    is_default = models.BooleanField(default=False)

    # Quotas
    max_bytes = models.BigIntegerField(default=10 * 1024 * 1024 * 1024)  # 10 GB
    max_files = models.IntegerField(default=20000)

    # Accounting (kept in sync on create/delete)
    used_bytes = models.BigIntegerField(default=0)
    file_count = models.IntegerField(default=0)

    class Meta:
        unique_together = (("owner", "slug"),)
        indexes = [models.Index(fields=["owner", "slug"])]

    def __str__(self):
        return f"{self.owner.name_spase}/{self.slug}" + (" *" if self.is_default else "")

class Asset(models.Model):
    """Files live inside a Space; bucket is the 'Main folder' chosen in UI."""
    space = models.ForeignKey(Space, on_delete=models.CASCADE, related_name="assets")
    bucket = models.CharField(max_length=64, db_index=True, default="assets")
    original_name = models.CharField(max_length=255)
    rel_path = models.CharField(max_length=512, default="")  # folder tree inside the bucket
    size = models.BigIntegerField()
    mime = models.CharField(max_length=128, default='application/octet-stream')
    is_public = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        unique_together = (("space", "bucket", "rel_path", "original_name"),)
        indexes = [
            models.Index(fields=["space", "bucket", "rel_path"]),
            models.Index(fields=["space", "bucket"]),
        ]

    def __str__(self):
        return f"{self.space.owner.name_spase}/{self.space.slug}/{self.bucket}/{self.rel_path}/{self.original_name}"

    @property
    def public_url(self) -> str:
        base = f"/cdn/{self.space.owner.name_spase}/{self.space.slug}/{self.bucket}"
        return f"{base}/{self.rel_path}/{self.original_name}" if self.rel_path else f"{base}/{self.original_name}"
