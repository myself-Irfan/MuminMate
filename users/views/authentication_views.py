from django.contrib.auth import views as auth_views
from django.contrib.auth.forms import AuthenticationForm
from django.core.exceptions import NON_FIELD_ERRORS
from django.http import HttpResponse

from users.forms.authentication_forms import ConsumerAuthenticationForm
from users.services.email_verification_service import EmailVerificationService


class ConsumerLoginView(auth_views.LoginView):
    authentication_form = ConsumerAuthenticationForm
    redirect_authenticated_user = True
    url_name = "login"

    # Only a correct password reaches this refusal, so the link goes to the owner.
    def form_invalid(self, form: AuthenticationForm) -> HttpResponse:
        if form.has_error(NON_FIELD_ERRORS, "email_unverified"):
            EmailVerificationService().resend(form.get_user())
        return super().form_invalid(form)


class ConsumerLogoutView(auth_views.LogoutView):
    url_name = "logout"
