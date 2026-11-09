from django.contrib.messages import constants
from django.contrib.messages.storage.base import Message
from django.template.loader import render_to_string


def test_message_banner_carries_its_level_as_class() -> None:
    html = render_to_string(
        "partials/messages.html",
        {"messages": [Message(constants.ERROR, "Too many."), Message(constants.SUCCESS, "Saved.")]},
    )

    assert '<p role="status" class="error">Too many.</p>' in html
    assert '<p role="status" class="success">Saved.</p>' in html
