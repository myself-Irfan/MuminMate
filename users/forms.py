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
