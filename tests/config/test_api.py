from http import HTTPStatus

import pytest
from django.test import Client

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
