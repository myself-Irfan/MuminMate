import pytest
from pydantic import ValidationError

from backend.threads.schemas import CreateThreadRequest, RenameThreadRequest


def test_create_thread_request_no_title():
    r = CreateThreadRequest()
    assert r.title is None


def test_create_thread_request_valid_title():
    r = CreateThreadRequest(title="My thread")
    assert r.title == "My thread"


def test_create_thread_request_title_whitespace_stripped():
    r = CreateThreadRequest(title="  My thread  ")
    assert r.title == "My thread"


def test_create_thread_request_blank_title():
    with pytest.raises(ValidationError, match="title cannot be blank"):
        CreateThreadRequest(title="   ")


def test_create_thread_request_title_too_long():
    with pytest.raises(ValidationError, match="at most 200 characters"):
        CreateThreadRequest(title="a" * 201)


def test_create_thread_request_title_exactly_max_length():
    r = CreateThreadRequest(title="a" * 200)
    assert len(r.title) == 200


def test_rename_thread_request_valid_title():
    r = RenameThreadRequest(title="New title")
    assert r.title == "New title"


def test_rename_thread_request_blank_title():
    with pytest.raises(ValidationError, match="title cannot be blank"):
        RenameThreadRequest(title="   ")


def test_rename_thread_request_title_too_long():
    with pytest.raises(ValidationError, match="at most 200 characters"):
        RenameThreadRequest(title="a" * 201)


def test_rename_thread_request_missing_title():
    with pytest.raises(ValidationError):
        RenameThreadRequest()  # type: ignore[call-arg]
