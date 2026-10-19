from django import forms
from django.contrib.auth import forms as auth_forms

from users.models import User


# Invite: the user sets the password from the invite email.
class UserAdminCreationForm(forms.ModelForm[User]):
    class Meta:
        model = User
        fields = ("email",)


class UserAdminChangeForm(auth_forms.UserChangeForm[User]):
    class Meta:
        model = User
        fields = "__all__"
