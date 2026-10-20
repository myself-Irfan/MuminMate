from django import forms

from users.models import User
from users.validators import validate_email_is_ascii


class ResendVerificationForm(forms.Form):
    email = forms.EmailField(
        max_length=User._meta.get_field("email").max_length,
        validators=[validate_email_is_ascii],
        widget=forms.EmailInput(attrs={"autocomplete": "email"}),
    )
