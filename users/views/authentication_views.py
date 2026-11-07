from django.contrib.auth import views as auth_views
from django.contrib.auth.forms import AuthenticationForm
from django.core.exceptions import NON_FIELD_ERRORS
from django.http import HttpResponse
from django.shortcuts import redirect

from users.forms.authentication_forms import ConsumerAuthenticationForm
from users.services.email_verification_service import EmailVerificationService


class ConsumerLoginView(auth_views.LoginView):
    authentication_form = ConsumerAuthenticationForm
    redirect_authenticated_user = True
    url_name = "login"

    def form_valid(self, form: AuthenticationForm) -> HttpResponse:
        # Read before super(): logging in fills last_login.
        is_first_login = form.get_user().last_login is None
        response = super().form_valid(form)
        if is_first_login and not self.get_redirect_url():
            return redirect("welcome")
        return response

    # Only a correct password reaches this refusal, so the link goes to the owner.
    def form_invalid(self, form: AuthenticationForm) -> HttpResponse:
        if form.has_error(NON_FIELD_ERRORS, "email_unverified"):
            EmailVerificationService().resend(form.get_user())
        return super().form_invalid(form)


class ConsumerLogoutView(auth_views.LogoutView):
    url_name = "logout"
