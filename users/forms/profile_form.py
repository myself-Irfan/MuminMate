from typing import Any, ClassVar

from django import forms
from django.utils import timezone

from users.enums import EmploymentStatus, Gender
from users.models import Profile


class ProfileForm(forms.ModelForm[Profile]):
    gender = forms.ChoiceField(choices=[("", "Prefer not to say"), *Gender.choices], required=False)
    employment_status = forms.ChoiceField(
        label="What do you mostly do these days?",
        choices=[("", "Choose one"), *EmploymentStatus.choices],
        required=False,
    )

    class Meta:
        model = Profile
        fields = ("display_name", "birth_date", "gender", "employment_status")
        labels: ClassVar[dict[str, str]] = {
            "display_name": "What should we call you?",
            "birth_date": "Date of birth",
        }
        help_texts: ClassVar[dict[str, str]] = {"display_name": "A first name or nickname is fine."}
        widgets: ClassVar[dict[str, forms.Widget]] = {
            "display_name": forms.TextInput(attrs={"autocomplete": "nickname"}),
            "birth_date": forms.DateInput(
                attrs={"type": "date", "min": "1900-01-01", "autocomplete": "bday"},
                format="%Y-%m-%d",
            ),
        }

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        # "Today" moves, so the picker's end is set per form, not once at import.
        self.fields["birth_date"].widget.attrs["max"] = timezone.localdate().isoformat()


class ProfileFieldForm(ProfileForm):
    def __init__(self, *args: Any, field: str, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        for name in list(self.fields):
            if name != field:
                del self.fields[name]
