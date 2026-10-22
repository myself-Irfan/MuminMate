from http import HTTPStatus

import django_stubs_ext
from django.contrib import messages
from django.contrib.auth import views as auth_views
from django.contrib.auth.forms import PasswordResetForm, SetPasswordForm, SetPasswordMixin
from django.db import transaction
from django.http import HttpResponse

from users.forms.password_reset_form import ConsumerPasswordResetForm
from users.models import User
from users.services.password_reset_service import PasswordResetService
from users.services.request_limit_service import RequestLimitService

# Lets SetPasswordForm[User] run; built into Django 6.0 (d0c8f89), delete on upgrade.
django_stubs_ext.monkeypatch(extra_classes=[SetPasswordMixin])


class ConsumerPasswordResetView(auth_views.PasswordResetView):
    form_class = ConsumerPasswordResetForm
    template_name = "registration/password_reset/form.html"
    url_name = "password_reset"

    # Counted per typed email, account or not, so the limit reveals no accounts.
    def form_valid(self, form: PasswordResetForm) -> HttpResponse:
        ip = self.request.META.get("REMOTE_ADDR")
        if not RequestLimitService().record_password_reset(form.cleaned_data["email"], ip):
            messages.error(self.request, "Too many reset requests for this email. Try again later.")
            return self.render_to_response(
                self.get_context_data(form=form), status=HTTPStatus.TOO_MANY_REQUESTS
            )
        return super().form_valid(form)


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
