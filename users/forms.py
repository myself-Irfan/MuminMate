from django import forms
from django.contrib.auth import forms as auth_forms

from users.models import User


class UserAdminCreationForm(auth_forms.AdminUserCreationForm[User]):
    class Meta:
        model = User
        fields = ("email",)


class UserAdminChangeForm(auth_forms.UserChangeForm[User]):
    class Meta:
        model = User
        fields = "__all__"


class ConsumerAuthenticationForm(auth_forms.AuthenticationForm):
    username = auth_forms.UsernameField(widget=forms.EmailInput(attrs={"autofocus": True}))

    def confirm_login_allowed(self, user: User) -> None:
        super().confirm_login_allowed(user)
        if user.is_privileged:
            raise self.get_invalid_login_error()
