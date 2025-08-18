from django.contrib import admin
from django.urls import path,include

from accounts.views import RememberLoginView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', RememberLoginView.as_view(), name='login'),
    path('', include('core.urls')),
    path('accounts/',include('accounts.urls'))
  # private gate
]
