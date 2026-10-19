import django_stubs_ext
from django.contrib.auth import views as auth_views
from django.contrib.auth.forms import SetPasswordForm, SetPasswordMixin
from django.db import transaction
from django.http import HttpResponse

from users.forms.password_reset_form import ConsumerPasswordResetForm
from users.models import User
from users.services.password_reset_service import PasswordResetService

# Lets SetPasswordForm[User] run; built into Django 6.0 (d0c8f89), delete on upgrade.
django_stubs_ext.monkeypatch(extra_classes=[SetPasswordMixin])


class ConsumerPasswordResetView(auth_views.PasswordResetView):
    form_class = ConsumerPasswordResetForm
    template_name = "registration/password_reset/form.html"
    url_name = "password_reset"


class ConsumerPasswordResetDoneView(auth_views.PasswordResetDoneView):
    template_name = "registration/password_reset/done.html"
    url_name = "password_reset_done"


class ConsumerPasswordResetConfirmView(auth_views.PasswordResetConfirmView):
    template_name = "registration/password_reset/confirm.html"
    url_name = "password_reset_confirm"

    def form_valid(self, form: SetPasswordForm[User]) -> HttpResponse:
        with transaction.atomic():
            response = super().form_valid(form)
            PasswordResetService().complete_reset(form.user, self.request.META.get("REMOTE_ADDR"))
        return response


class ConsumerPasswordResetCompleteView(auth_views.PasswordResetCompleteView):
    template_name = "registration/password_reset/complete.html"
    url_name = "password_reset_complete"
