from django.urls import path
from core.views import dashboard, api_upload, api_assets, api_allowed_extensions, api_zip, api_browse, \
    api_mkdir, api_rename, api_delete, api_delete_batch, api_space_set, api_spaces

urlpatterns = [
    path('dashboard/', dashboard, name='dashboard'),
    path('api/spaces', api_spaces, name='api_spaces'),
    path('api/space/set', api_space_set, name='api_space_set'),

    path('api/allowed-extensions', api_allowed_extensions, name='api_allowed_extensions'),
    path('api/assets', api_assets, name='api_assets'),
    path('api/browse', api_browse, name='api_browse'),

    path('api/upload', api_upload, name='api_upload'),
    path('api/zip', api_zip, name='api_zip'),

    path('api/mkdir', api_mkdir, name='api_mkdir'),
    path('api/rename', api_rename, name='api_rename'),
    path('api/delete', api_delete, name='api_delete'),
    path('api/delete-batch', api_delete_batch, name='api_delete_batch'),
]