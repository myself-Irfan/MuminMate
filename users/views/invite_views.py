import django_stubs_ext
from django.contrib import messages
from django.contrib.auth import views as auth_views
from django.contrib.auth.forms import SetPasswordForm, SetPasswordMixin
from django.db import transaction
from django.http import HttpResponse
from django.urls import reverse

from core.client_ip import get_client_ip
from users.models import User
from users.services.invite_service import InviteService
from users.tokens import InviteTokenGenerator

# Lets SetPasswordForm[User] run; built into Django 6.0 (d0c8f89), delete on upgrade.
django_stubs_ext.monkeypatch(extra_classes=[SetPasswordMixin])


# Django's set-password machinery; staff and consumers log in at different doors.
class ConsumerInviteConfirmView(auth_views.PasswordResetConfirmView):
    template_name = "registration/invite/confirm.html"
    url_name = "invite_confirm"
    token_generator = InviteTokenGenerator()

    def form_valid(self, form: SetPasswordForm[User]) -> HttpResponse:
        with transaction.atomic():
            response = super().form_valid(form)
            InviteService().accept(form.user, get_client_ip(self.request))
        messages.success(self.request, "Your password is set. Log in to continue.")
        return response

    def get_success_url(self) -> str:
        if isinstance(self.user, User) and self.user.is_privileged:
            return reverse("admin:login")
        return reverse("login")
