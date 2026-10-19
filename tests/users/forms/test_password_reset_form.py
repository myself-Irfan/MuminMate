import io
from unittest.mock import Mock

import pytest
from django.test import RequestFactory

from tests.logging_support import events
from users.forms.password_reset_form import ConsumerPasswordResetForm
from users.models import User


@pytest.fixture
def request_password_reset(monkeypatch: pytest.MonkeyPatch) -> Mock:
    request_reset = Mock()
    monkeypatch.setattr(
        "users.forms.password_reset_form.UserService.request_password_reset", request_reset
    )
    return request_reset


def test_password_reset_form_requests_reset_for_consumer(
    rf: RequestFactory, request_password_reset: Mock, consumer_user: User
) -> None:
    form = ConsumerPasswordResetForm(data={"email": consumer_user.email.upper()})
    assert form.is_valid()

    form.save(request=rf.get("/"))

    request_password_reset.assert_called_once_with(consumer_user.pk)


@pytest.mark.django_db
def test_password_reset_form_logs_unknown_email(
    json_logs: io.StringIO, rf: RequestFactory, request_password_reset: Mock
) -> None:
    form = ConsumerPasswordResetForm(data={"email": "nobody@example.com"})
    assert form.is_valid()

    form.save(request=rf.get("/"))

    request_password_reset.assert_not_called()
    [line] = events(json_logs, "password_reset_requested")
    assert line["user_id"] is None


def test_password_reset_form_refuses_privileged_user(
    json_logs: io.StringIO, rf: RequestFactory, request_password_reset: Mock, privileged_user: User
) -> None:
    form = ConsumerPasswordResetForm(data={"email": privileged_user.email})
    assert form.is_valid()

    form.save(request=rf.get("/"))

    request_password_reset.assert_not_called()
    [line] = events(json_logs, "password_reset_refused")
    assert (line["level"], line["reason"], line["user_id"]) == (
        "warning",
        "privileged_account",
        privileged_user.pk,
    )
