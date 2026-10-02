from http import HTTPStatus

import pytest
from django.test import Client

from users.models import User


@pytest.mark.django_db
def test_page_redirects_to_login_when_anonymous(client: Client) -> None:
    response = client.get("/")

    assert response.status_code == HTTPStatus.FOUND
    assert response["Location"] == "/accounts/login/?next=/"


def test_page_opens_for_consumer(client: Client, consumer_user: User) -> None:
    client.force_login(consumer_user)

    response = client.get("/")

    assert response.status_code == HTTPStatus.OK


@pytest.mark.django_db
def test_login_page_opens_when_anonymous(client: Client) -> None:
    response = client.get("/accounts/login/")

    assert response.status_code == HTTPStatus.OK


@pytest.mark.django_db
def test_admin_keeps_its_own_login_when_anonymous(client: Client) -> None:
    response = client.get("/admin/")

    assert response.status_code == HTTPStatus.FOUND
    assert response["Location"] == "/admin/login/?next=/admin/"


@pytest.mark.django_db
def test_api_is_not_redirected_when_anonymous(client: Client) -> None:
    response = client.get("/api/health/live")

    assert response.status_code == HTTPStatus.OK


def test_page_redirects_privileged_user_to_admin(client: Client, privileged_user: User) -> None:
    client.force_login(privileged_user)

    response = client.get("/")

    assert response.status_code == HTTPStatus.FOUND
    assert response["Location"] == "/admin/"
