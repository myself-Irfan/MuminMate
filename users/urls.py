from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_not_required
from django.urls import path
from django.views.generic import TemplateView

from users.forms import ConsumerAuthenticationForm
from users.views import SignupView

urlpatterns = [
    path(
        "login/",
        auth_views.LoginView.as_view(
            authentication_form=ConsumerAuthenticationForm, redirect_authenticated_user=True
        ),
        name="login",
    ),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("signup/", SignupView.as_view(), name=SignupView.url_name),
    path(
        "signup/done/",
        login_not_required(TemplateView.as_view(template_name="registration/signup_done.html")),
        name="signup_done",
    ),
]
