from http import HTTPStatus
from typing import Any

from django.contrib import messages
from django.contrib.auth.decorators import login_not_required
from django.core.exceptions import ValidationError
from django.http import HttpRequest, HttpResponse, HttpResponseBase
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.utils.decorators import method_decorator
from django.views.generic import FormView, TemplateView

from core.client_ip import get_client_ip
from users.exceptions import EmailTakenError
from users.forms.signup_form import SignupForm
from users.services.request_limit_service import RequestLimitService
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

    def post(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        if not RequestLimitService().record_signup(get_client_ip(request)):
            messages.error(request, "Too many sign-up attempts from your network. Try again later.")
            # Unvalidated form: its errors would say whether the email is taken.
            form = self.get_form_class()(initial={"email": request.POST.get("email", "")})
            return self.render_to_response(
                self.get_context_data(form=form), status=HTTPStatus.TOO_MANY_REQUESTS
            )
        return super().post(request, *args, **kwargs)

    def form_valid(self, form: SignupForm) -> HttpResponse:
        email = form.cleaned_data["email"]
        try:
            UserService().signup(email=email, password=form.cleaned_data["password1"])
        except EmailTakenError:
            form.add_error(
                "email",
                ValidationError(form.fields["email"].error_messages["unique"], code="unique"),
            )
            return self.form_invalid(form)
        return super().form_valid(form)


@method_decorator(login_not_required, name="dispatch")
class SignupDoneView(TemplateView):
    template_name = "registration/signup_done.html"
    url_name = "signup_done"
