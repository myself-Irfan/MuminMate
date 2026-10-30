from http import HTTPStatus
from unittest.mock import Mock

import pytest
from django.test import Client

from users.models import User


def test_unhandled_error_recorded_in_response_event(
    monkeypatch: pytest.MonkeyPatch, audit_publish: Mock
) -> None:
    monkeypatch.setattr(
        "core.api.HealthService.is_db_ready", Mock(side_effect=RuntimeError("db probe broke"))
    )

    Client(raise_request_exception=False).get("/api/health/ready")

    response_event = audit_publish.call_args.args[0]
    assert response_event["status"] == HTTPStatus.INTERNAL_SERVER_ERROR
    assert response_event["error"]["error_type"] == "RuntimeError"


@pytest.mark.django_db
def test_logout_recorded_with_user_who_logged_out(
    client: Client, consumer_user: User, audit_publish: Mock
) -> None:
    client.force_login(consumer_user)

    client.post("/accounts/logout/")

    assert audit_publish.call_args.args[0]["user_id"] == consumer_user.pk
