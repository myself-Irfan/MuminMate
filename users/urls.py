from django.contrib.auth import views as auth_views
from django.urls import path

from users.forms import ConsumerAuthenticationForm
from users.views import SignupDoneView, SignupView, VerifyEmailView

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
    path("signup/done/", SignupDoneView.as_view(), name=SignupDoneView.url_name),
    path(
        "verify/<uidb64>/<token>/",
        VerifyEmailView.as_view(),
        name=VerifyEmailView.url_name,
    ),
]
