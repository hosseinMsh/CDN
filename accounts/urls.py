from django.urls import path

from accounts.views import RememberLoginView,RememberLogoutView

urlpatterns = [

    # Auth pages
    path('login/', RememberLoginView.as_view(), name='login'),
    path('logout/', RememberLogoutView.as_view(), name='logout'),

]
