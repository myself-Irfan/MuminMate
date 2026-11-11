import pytest

from chats.titles import make_title


def test_short_message_is_the_title() -> None:
    assert make_title("Exam stress") == "Exam stress"


def test_whitespace_collapses_to_single_spaces() -> None:
    assert make_title("  Exam\n\nstress \t tonight ") == "Exam stress tonight"


@pytest.mark.parametrize("length", [59, 60])
def test_title_up_to_60_characters_is_kept_whole(length: int) -> None:
    assert make_title("a" * length) == "a" * length


def test_long_message_is_cut_on_a_word_with_ellipsis() -> None:
    message = "I've been feeling really anxious before my exams and I can't sleep properly at night"

    assert make_title(message) == (
        "I've been feeling really anxious before my exams and I can't\N{HORIZONTAL ELLIPSIS}"
    )


def test_cut_inside_a_word_drops_that_word() -> None:
    assert make_title("a" * 55 + " abcdefgh") == "a" * 55 + "\N{HORIZONTAL ELLIPSIS}"


def test_long_word_is_cut_at_60_with_ellipsis() -> None:
    assert make_title("a" * 80) == "a" * 60 + "\N{HORIZONTAL ELLIPSIS}"
