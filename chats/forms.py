from typing import Any, ClassVar

from django import forms
from django.conf import settings
from django.core.validators import MaxLengthValidator
from django.utils.text import normalize_newlines

from chats.models import Thread


# Browsers count a line break as 1 for maxlength but post it as \r\n.
class MessageField(forms.CharField):
    def to_python(self, value: Any | None) -> str | None:
        text = super().to_python(value)
        return None if text is None else normalize_newlines(text)


class ThreadRenameForm(forms.ModelForm[Thread]):
    class Meta:
        model = Thread
        fields = ("title",)
        error_messages: ClassVar[dict[str, dict[str, str]]] = {
            "title": {"required": "Enter a title."}
        }
        widgets: ClassVar[dict[str, forms.Widget]] = {
            "title": forms.TextInput(attrs={"autofocus": True})
        }


class MessageForm(forms.Form):
    content = MessageField(
        label="Message",
        widget=forms.Textarea(
            attrs={"rows": 1, "placeholder": "Write a message\N{HORIZONTAL ELLIPSIS}"}
        ),
        error_messages={"required": "Write a message."},
    )

    # Read per form, not at import, so `override_settings` applies.
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        field = self.fields["content"]
        field.validators.append(MaxLengthValidator(settings.MESSAGE_MAX_LENGTH))
        field.widget.attrs["maxlength"] = str(settings.MESSAGE_MAX_LENGTH)
