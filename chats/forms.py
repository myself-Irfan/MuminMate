from typing import ClassVar

from django import forms

from chats.models import Thread


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
