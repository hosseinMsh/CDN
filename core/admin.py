from django.contrib import admin
from core.models import AllowedExtension, Space, Asset


@admin.register(AllowedExtension)
class AllowedExtAdmin(admin.ModelAdmin):
    list_display = ("ext", "enabled", "description", "created_at")
    list_filter = ("enabled",)
    search_fields = ("ext", "description")


@admin.register(Space)
class SpaceAdmin(admin.ModelAdmin):
    list_display = ("owner", "name", "slug", "is_default", "used_bytes", "file_count", "max_bytes", "max_files")
    list_filter = ("is_default",)
    search_fields = ("owner__username", "owner__name_spase", "name", "slug")
    readonly_fields = ("used_bytes", "file_count")


@admin.register(Asset)
class AssetAdmin(admin.ModelAdmin):
    list_display = ("space", "rel_path", "original_name", "size", "mime", "created_at")
    search_fields = ("original_name", "rel_path", "space__owner__username", "space__slug", "mime")
    list_filter = ("space",)
