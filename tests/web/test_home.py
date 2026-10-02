from http import HTTPStatus

import pytest
from django.test import Client
from pytest_django.asserts import assertContains, assertNotContains

from users.models import User


@pytest.mark.django_db
def test_home_links_to_login_when_anonymous(client: Client) -> None:
    response = client.get("/")

    assert response.status_code == HTTPStatus.OK
    assertContains(response, 'href="/accounts/login/"')
    assertNotContains(response, 'action="/accounts/logout/"')


def test_home_shows_email_and_logout_when_logged_in(client: Client, consumer_user: User) -> None:
    client.force_login(consumer_user)

    response = client.get("/")

    assertContains(response, consumer_user.email)
    assertContains(response, 'action="/accounts/logout/"')


@pytest.mark.django_db
def test_home_loads_pico_and_theme_stylesheets(client: Client) -> None:
    response = client.get("/")

    assertContains(response, 'href="/static/vendor/pico/pico.fluid.classless.min.css"')
    assertContains(response, 'href="/static/css/theme.css"')
