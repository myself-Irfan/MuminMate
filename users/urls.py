from django.urls import path

from users.views.authentication_views import ConsumerLoginView, ConsumerLogoutView
from users.views.email_verification_views import VerifyEmailView
from users.views.invite_views import ConsumerInviteConfirmView
from users.views.password_reset_views import (
    ConsumerPasswordResetCompleteView,
    ConsumerPasswordResetConfirmView,
    ConsumerPasswordResetDoneView,
    ConsumerPasswordResetView,
)
from users.views.signup_views import SignupDoneView, SignupView

urlpatterns = [
    path("login/", ConsumerLoginView.as_view(), name=ConsumerLoginView.url_name),
    path("logout/", ConsumerLogoutView.as_view(), name=ConsumerLogoutView.url_name),
    path("signup/", SignupView.as_view(), name=SignupView.url_name),
    path("signup/done/", SignupDoneView.as_view(), name=SignupDoneView.url_name),
    path(
        "verify/<uidb64>/<token>/",
        VerifyEmailView.as_view(),
        name=VerifyEmailView.url_name,
    ),
    path(
        "password-reset/",
        ConsumerPasswordResetView.as_view(),
        name=ConsumerPasswordResetView.url_name,
    ),
    path(
        "password-reset/done/",
        ConsumerPasswordResetDoneView.as_view(),
        name=ConsumerPasswordResetDoneView.url_name,
    ),
    path(
        "password-reset/<uidb64>/<token>/",
        ConsumerPasswordResetConfirmView.as_view(),
        name=ConsumerPasswordResetConfirmView.url_name,
    ),
    path(
        "password-reset/complete/",
        ConsumerPasswordResetCompleteView.as_view(),
        name=ConsumerPasswordResetCompleteView.url_name,
    ),
    path(
        "invite/<uidb64>/<token>/",
        ConsumerInviteConfirmView.as_view(),
        name=ConsumerInviteConfirmView.url_name,
    ),
]
