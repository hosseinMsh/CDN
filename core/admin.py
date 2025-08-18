from django.contrib import admin
from .models import AllowedExtension, Asset

@admin.register(AllowedExtension)
class AllowedExtensionAdmin(admin.ModelAdmin):
    list_display = ("ext", "enabled", "description", "created_at")
    list_filter = ("enabled",)
    search_fields = ("ext", "description")

@admin.register(Asset)
class AssetAdmin(admin.ModelAdmin):
    list_display = ("bucket", "hashed_name", "size", "mime", "created_at")
    list_filter = ("bucket", "mime", "created_at")
    search_fields = ("original_name", "hashed_name", "content_sha256")