from django.contrib import admin
from .models import AllowedExtension, Asset

@admin.register(AllowedExtension)
class AllowedExtensionAdmin(admin.ModelAdmin):
    list_display = ("ext", "enabled", "description", "created_at")
    list_filter = ("enabled",)
    search_fields = ("ext", "description")

@admin.register(Asset)
class AssetAdmin(admin.ModelAdmin):
    list_display = ("owner", "bucket", "rel_path", "original_name", "size", "mime", "created_at")
    list_filter = ("bucket", "mime", "created_at")
    search_fields = ("original_name", "rel_path", "owner__username", "owner__name_spase")