from django.urls import path
from core.views import dashboard, api_upload, api_assets, api_allowed_extensions

urlpatterns = [
    path('dashboard/', dashboard, name='dashboard'),
    path('api/upload', api_upload, name='api_upload'),
    path('api/assets', api_assets, name='api_assets'),
    path('api/allowed-extensions', api_allowed_extensions, name='api_allowed_extensions'),
]