from typing import Any

from django.contrib import messages
from django.contrib.auth.decorators import login_not_required
from django.core.exceptions import ValidationError
from django.http import HttpRequest, HttpResponse, HttpResponseBase
from django.shortcuts import redirect
from django.template.response import TemplateResponse
from django.urls import reverse_lazy
from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache
from django.views.generic import FormView, TemplateView

from users.exceptions import EmailTakenError, InvalidVerificationLinkError
from users.forms import SignupForm
from users.services.email_verification_service import EmailVerificationService
from users.services.user_service import UserService


@method_decorator(login_not_required, name="dispatch")
class SignupView(FormView[SignupForm]):
    form_class = SignupForm
    template_name = "registration/signup.html"
    url_name = "signup"
    success_url = reverse_lazy("signup_done")

    def dispatch(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponseBase:
        if request.user.is_authenticated:
            return redirect("home")
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form: SignupForm) -> HttpResponse:
        try:
            UserService().signup(
                email=form.cleaned_data["email"], password=form.cleaned_data["password1"]
            )
        except EmailTakenError:
            form.add_error(
                "email",
                ValidationError(
                    form.fields["email"].error_messages["email_taken"], code="email_taken"
                ),
            )
            return self.form_invalid(form)
        return super().form_valid(form)


@method_decorator(login_not_required, name="dispatch")
class SignupDoneView(TemplateView):
    template_name = "registration/signup_done.html"
    url_name = "signup_done"


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
