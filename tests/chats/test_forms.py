import pytest

from chats.forms import MessageForm


@pytest.mark.usefixtures("message_max_length_five")
def test_message_form_counts_posted_line_break_as_one_character() -> None:
    form = MessageForm(data={"content": "ab\r\ncd"})

    assert form.is_valid()
    assert form.cleaned_data["content"] == "ab\ncd"


def test_message_form_turns_lone_carriage_return_into_line_break() -> None:
    form = MessageForm(data={"content": "ab\rcd"})

    assert form.is_valid()
    assert form.cleaned_data["content"] == "ab\ncd"
