import json
from http import HTTPStatus

import pytest
from django.http import Http404
from django.test import Client, RequestFactory
from ninja.errors import AuthenticationError, AuthorizationError, Throttled, ValidationError

from config.api import api
from users.models import User


def test_every_api_operation_requires_auth_except_health() -> None:
    schema = api.get_openapi_schema()

    public = {
        (path, method)
        for path, operations in schema["paths"].items()
        for method, operation in operations.items()
        if not operation.get("security")
    }

    assert public == {("/api/health/live", "get"), ("/api/health/ready", "get")}


@pytest.mark.django_db
@pytest.mark.parametrize("path", ["/api/docs", "/api/openapi.json"])
def test_docs_redirect_to_admin_login_when_anonymous(client: Client, path: str) -> None:
    response = client.get(path)

    assert response.status_code == HTTPStatus.FOUND
    assert response["Location"].startswith("/admin/login/")


@pytest.mark.parametrize("path", ["/api/docs", "/api/openapi.json"])
def test_docs_redirect_to_admin_login_when_consumer(
    client: Client, consumer_user: User, path: str
) -> None:
    client.force_login(consumer_user)

    response = client.get(path)

    assert response.status_code == HTTPStatus.FOUND
    assert response["Location"].startswith("/admin/login/")


def test_docs_open_for_staff(client: Client, staff_user: User) -> None:
    client.force_login(staff_user)

    response = client.get("/api/docs")

    assert response.status_code == HTTPStatus.OK


@pytest.mark.parametrize(
    ("error", "status", "detail"),
    [
        (AuthenticationError(), HTTPStatus.UNAUTHORIZED, "Unauthorized"),
        (AuthorizationError(), HTTPStatus.FORBIDDEN, "Forbidden"),
        (Throttled(wait=None), HTTPStatus.TOO_MANY_REQUESTS, "Too many requests."),
        (Http404(), HTTPStatus.NOT_FOUND, "Not found."),
    ],
    ids=["unauthorized", "forbidden", "throttled", "not_found"],
)
def test_ninja_errors_rendered_as_problem(
    rf: RequestFactory, error: Exception, status: HTTPStatus, detail: str
) -> None:
    response = api.on_exception(rf.get("/api/"), error)

    assert response.status_code == status
    assert response["Content-Type"] == "application/problem+json"
    assert json.loads(response.content) == {
        "type": "about:blank",
        "title": status.phrase,
        "status": status,
        "detail": detail,
    }


# The submitted input is dropped: it could be a password.
def test_validation_error_rendered_as_problem_with_field_errors(rf: RequestFactory) -> None:
    error = ValidationError(
        [{"type": "missing", "loc": ("body", "email"), "msg": "Field required", "input": "secret"}]
    )

    response = api.on_exception(rf.post("/api/"), error)

    assert response.status_code == HTTPStatus.UNPROCESSABLE_CONTENT
    assert response["Content-Type"] == "application/problem+json"
    assert json.loads(response.content) == {
        "type": "about:blank",
        "title": "Unprocessable Content",
        "status": 422,
        "detail": "The request has invalid fields.",
        "errors": [{"type": "missing", "loc": ["body", "email"], "msg": "Field required"}],
    }
