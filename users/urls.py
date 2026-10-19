from django.urls import path

from users.views import (
    ConsumerLoginView,
    ConsumerLogoutView,
    ConsumerPasswordResetCompleteView,
    ConsumerPasswordResetConfirmView,
    ConsumerPasswordResetDoneView,
    ConsumerPasswordResetView,
    SignupDoneView,
    SignupView,
    VerifyEmailView,
)

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
]
