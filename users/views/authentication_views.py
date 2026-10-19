from django.contrib.auth import views as auth_views

from users.forms.authentication_forms import ConsumerAuthenticationForm


class ConsumerLoginView(auth_views.LoginView):
    authentication_form = ConsumerAuthenticationForm
    redirect_authenticated_user = True
    url_name = "login"


class ConsumerLogoutView(auth_views.LogoutView):
    url_name = "logout"
