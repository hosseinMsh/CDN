from django.contrib.auth.views import LoginView
from django.contrib.auth import logout
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.views import View
class RememberLoginView(LoginView):
    template_name = "accounts/login.html"
    redirect_authenticated_user = True

    def form_valid(self, form):
        # if "remember" not checked -> expire at browser close
        if not bool(self.request.POST.get("remember")):
            self.request.session.set_expiry(0)
        else:
            # 14 days
            self.request.session.set_expiry(14 * 24 * 3600)
        return super().form_valid(form)




class RememberLogoutView(View):
    """
    Logout by GET (like your custom login)
    """
    next_page = reverse_lazy("login")
    def get(self, request, *args, **kwargs):
        logout(request)
        return redirect(self.next_page)
