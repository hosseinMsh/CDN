from django.urls import path, include
from django.contrib.auth.views import  LogoutView

from accounts.views import RememberLoginView

urlpatterns = [

    # Auth pages
    path('login/', RememberLoginView.as_view(), name='login'),
    path('logout/', LogoutView.as_view(), name='logout'),

]
