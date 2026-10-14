import io
import uuid
from http import HTTPStatus

import pytest
from django.test import Client

from tests.logging_support import json_lines


def test_request_id_echoed_when_client_sends_valid_one(client: Client) -> None:
    response = client.get("/api/health/live", headers={"X-Request-ID": "client-id.1_a"})

    assert response["X-Request-ID"] == "client-id.1_a"


def test_request_id_generated_when_missing(client: Client) -> None:
    response = client.get("/api/health/live")

    assert uuid.UUID(response["X-Request-ID"])


@pytest.mark.parametrize("bad_id", ["has spaces", "a" * 129, "semi;colon", ""])
def test_request_id_replaced_when_malformed(client: Client, bad_id: str) -> None:
    response = client.get("/api/health/live", headers={"X-Request-ID": bad_id})

    assert uuid.UUID(response["X-Request-ID"])


def test_request_id_on_404(client: Client) -> None:
    response = client.get("/api/nope", headers={"X-Request-ID": "abc"})

    assert response.status_code == HTTPStatus.NOT_FOUND
    assert response["X-Request-ID"] == "abc"


@pytest.mark.urls("tests.urls")
def test_request_id_on_500() -> None:
    client = Client(raise_request_exception=False)

    response = client.get("/test/crash", headers={"X-Request-ID": "crash-1"})

    assert response.status_code == HTTPStatus.INTERNAL_SERVER_ERROR
    assert response["X-Request-ID"] == "crash-1"


def test_request_id_logged_is_the_replaced_one(client: Client, json_logs: io.StringIO) -> None:
    response = client.get("/api/nope", headers={"X-Request-ID": "has spaces"})

    assert {line["request_id"] for line in json_lines(json_logs)} == {response["X-Request-ID"]}


def test_correlation_id_not_logged(client: Client, json_logs: io.StringIO) -> None:
    client.get("/api/nope", headers={"X-Correlation-ID": "fake\nlog line"})

    assert all("correlation_id" not in line for line in json_lines(json_logs))
