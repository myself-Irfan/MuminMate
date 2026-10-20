from typing import Any

from django.contrib import messages
from django.contrib.auth.decorators import login_not_required
from django.http import HttpRequest, HttpResponse, HttpResponseBase
from django.shortcuts import redirect
from django.template.response import TemplateResponse
from django.urls import reverse_lazy
from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache
from django.views.generic import FormView, TemplateView

from users.exceptions import InvalidVerificationLinkError
from users.forms.resend_verification_form import ResendVerificationForm
from users.services.email_verification_service import EmailVerificationService


@method_decorator([login_not_required, never_cache], name="dispatch")
class VerifyEmailView(TemplateView):
    template_name = "registration/verify_email.html"
    invalid_template_name = "registration/verify_email_invalid.html"
    url_name = "verify_email"

    def dispatch(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponseBase:
        response = super().dispatch(request, *args, **kwargs)
        # OWASP: the URL holds the token; send it to no other site.
        response.headers["Referrer-Policy"] = "same-origin"
        return response

    def get(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        verification = EmailVerificationService()
        if not verification.is_link_valid(uidb64=kwargs["uidb64"], token=kwargs["token"]):
            return TemplateResponse(request, self.invalid_template_name)
        return self.render_to_response(self.get_context_data())

    def post(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        try:
            EmailVerificationService().verify(uidb64=kwargs["uidb64"], token=kwargs["token"])
        except InvalidVerificationLinkError:
            return TemplateResponse(request, self.invalid_template_name)
        messages.success(request, "Your email is confirmed. Log in to continue.")
        return redirect("login")


@method_decorator(login_not_required, name="dispatch")
class ResendVerificationView(FormView[ResendVerificationForm]):
    form_class = ResendVerificationForm
    template_name = "registration/resend_verification/form.html"
    url_name = "resend_verification"
    success_url = reverse_lazy("resend_verification_done")

    def form_valid(self, form: ResendVerificationForm) -> HttpResponse:
        EmailVerificationService().request_resend(form.cleaned_data["email"])
        return super().form_valid(form)


@method_decorator(login_not_required, name="dispatch")
class ResendVerificationDoneView(TemplateView):
    template_name = "registration/resend_verification/done.html"
    url_name = "resend_verification_done"
