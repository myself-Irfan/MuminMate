from http import HTTPStatus
from typing import Any

from django import forms
from django.contrib import messages
from django.contrib.auth import logout, update_session_auth_hash
from django.contrib.auth.forms import PasswordChangeForm
from django.http import HttpResponse, HttpResponseBadRequest
from django.shortcuts import redirect
from django.utils.decorators import method_decorator
from django.views.decorators.debug import sensitive_post_parameters
from django.views.generic import TemplateView

from users.forms.email_change_form import EmailChangeForm
from users.http import AuthenticatedHttpRequest
from users.services.email_change_service import EmailChangeService
from users.services.password_change_service import PasswordChangeService
from users.services.profile_service import ProfileService


# Like Django's PasswordChangeView: passwords never appear in error reports.
@method_decorator(sensitive_post_parameters(), name="dispatch")
class AccountSettingsView(TemplateView):
    request: AuthenticatedHttpRequest
    template_name = "users/account_settings.html"
    url_name = "account_settings"

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        return super().get_context_data(
            profile=ProfileService().get_profile(self.request.user),
            forms={
                "email": EmailChangeForm(self.request.user),
                "password": PasswordChangeForm(self.request.user),
            },
            open_row="",
            **kwargs,
        )

    def post(self, request: AuthenticatedHttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        row = request.POST.get("row", "")
        if row == "email":
            return self._change_email(request)
        if row == "password":
            return self._change_password(request)
        return HttpResponseBadRequest()

    def _change_email(self, request: AuthenticatedHttpRequest) -> HttpResponse:
        changes = EmailChangeService()
        attempt = changes.record_attempt(request.user)
        if attempt is None:
            return self._log_out(request)
        form = EmailChangeForm(request.user, request.POST)
        if not form.has_error("current_password", "password_incorrect"):
            changes.clear_attempt(attempt)
        if not form.is_valid():
            return self._render_row("email", form)
        if not changes.request_change(request.user, form.cleaned_data["email"]):
            messages.error(request, "Too many email change requests. Try again later.")
            return self._render_row("email", form, status=HTTPStatus.TOO_MANY_REQUESTS)
        messages.success(
            request,
            f"We sent a link to {form.cleaned_data['email']}. Open it to finish the change.",
        )
        return redirect(self.url_name)

    def _change_password(self, request: AuthenticatedHttpRequest) -> HttpResponse:
        changes = PasswordChangeService()
        attempt = changes.record_attempt(request.user)
        if attempt is None:
            return self._log_out(request)
        form = PasswordChangeForm(request.user, request.POST)
        if not form.has_error("old_password", "password_incorrect"):
            changes.clear_attempt(attempt)
        if not form.is_valid():
            return self._render_row("password", form)
        form.save()
        # Keeps this session; other sessions fail Django's session hash check and log out.
        update_session_auth_hash(request, form.user)
        changes.complete_change(form.user)
        messages.success(request, "Your password is changed.")
        return redirect(self.url_name)

    def _render_row(
        self, row: str, form: forms.Form, status: HTTPStatus = HTTPStatus.OK
    ) -> HttpResponse:
        context = self.get_context_data()
        context["forms"][row] = form
        context["open_row"] = row
        return self.render_to_response(context, status=status)

    # One wrong-password count for both rows; logging out replaces a cooldown.
    def _log_out(self, request: AuthenticatedHttpRequest) -> HttpResponse:
        logout(request)
        messages.error(
            request,
            "Too many wrong passwords. Log in again; to change your email or password today,"
            " reset your password first.",
        )
        return redirect("login")
