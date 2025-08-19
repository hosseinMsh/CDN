from django.contrib import admin
from django.urls import path, include

from accounts.views import RememberLoginView
from core.views import dashboard

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', RememberLoginView.as_view(), name='login'),
    path('dashboard/', dashboard, name='dashboard'),
    path('api/', include('core.urls')),
    path('accounts/', include('accounts.urls'))

]