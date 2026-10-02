from django.contrib.auth import views as auth_views
from django.urls import path

from users.forms import ConsumerAuthenticationForm

urlpatterns = [
    path(
        "login/",
        auth_views.LoginView.as_view(
            authentication_form=ConsumerAuthenticationForm, redirect_authenticated_user=True
        ),
        name="login",
    ),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
]
