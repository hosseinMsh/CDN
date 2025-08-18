from django.urls import path
from core.views import dashboard, api_upload, api_assets, api_allowed_extensions, api_zip, api_browse, api_file_private, \
    api_mkdir, api_rename, api_delete

urlpatterns = [
    path('dashboard/', dashboard, name='dashboard'),
    path('api/upload', api_upload, name='api_upload'),
    path('api/assets', api_assets, name='api_assets'),
    path('api/allowed-extensions', api_allowed_extensions, name='api_allowed_extensions'),
    path('api/browse', api_browse, name='api_browse'),
    path('api/zip', api_zip, name='api_zip'),
    path('api/file', api_file_private, name='api_file_private'),
    path('api/mkdir', api_mkdir, name='api_mkdir'),  # NEW
    path('api/rename', api_rename, name='api_rename'),  # NEW
    path('api/delete', api_delete, name='api_delete'),  # NEW
]