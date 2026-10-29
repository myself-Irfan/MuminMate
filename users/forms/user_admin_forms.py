from typing import Any

from django import forms
from django.contrib.auth import forms as auth_forms

from users.models import User


# An invite: the user sets the password from the emailed link.
class UserAdminCreationForm(forms.ModelForm[User]):
    class Meta:
        model = User
        fields = ("email", "is_staff")


class UserAdminChangeForm(auth_forms.UserChangeForm[User]):
    class Meta:
        model = User
        fields = "__all__"

    # Sides never switch; only staff are superusers. Disabled, not read-only: constraints still run.
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        if "is_staff" in self.fields:
            self.fields["is_staff"].disabled = True
        if "is_superuser" in self.fields:
            self.fields["is_superuser"].disabled = not self.instance.is_staff
