from http import HTTPStatus
from unittest.mock import Mock

import pytest
from django.test import Client
from pytest_django.asserts import assertContains

from users.models import User


@pytest.fixture
def signup_payload(password: str) -> dict[str, str]:
    return {"email": "new@example.com", "password1": password, "password2": password}


@pytest.mark.django_db
def test_signup_page_shows_form(client: Client) -> None:
    response = client.get("/accounts/signup/")

    assert response.status_code == HTTPStatus.OK
    assertContains(response, 'type="email" name="email"')


@pytest.mark.django_db
def test_signup_page_shows_password_hint_below_input(client: Client) -> None:
    html = client.get("/accounts/signup/").content.decode()

    assert html.index('id="id_password1"') < html.index('<small id="id_password1_helptext">')


@pytest.mark.django_db
def test_signup_page_labels_have_no_colon(client: Client) -> None:
    response = client.get("/accounts/signup/")

    assertContains(response, '<label for="id_email">Email</label>', html=True)


@pytest.mark.django_db
def test_signup_creates_user_and_redirects_to_done(
    client: Client, signup_payload: dict[str, str]
) -> None:
    response = client.post("/accounts/signup/", signup_payload)

    assert response.status_code == HTTPStatus.FOUND
    assert response["Location"] == "/accounts/signup/done/"
    assert User.objects.filter(email="new@example.com").exists()


def test_signup_shows_error_when_email_taken(
    client: Client, consumer_user: User, signup_payload: dict[str, str]
) -> None:
    signup_payload["email"] = consumer_user.email.upper()

    response = client.post("/accounts/signup/", signup_payload)

    assertContains(response, "An account with this email already exists.")
    assert response.context["form"].has_error("email", "unique")
    assert User.objects.count() == 1


# The form's check passed, then another signup committed first.
def test_signup_shows_error_when_parallel_signup_wins(
    monkeypatch: pytest.MonkeyPatch,
    client: Client,
    consumer_user: User,
    signup_payload: dict[str, str],
) -> None:
    monkeypatch.setattr("users.forms.signup_form.SignupForm.validate_unique", Mock())
    signup_payload["email"] = consumer_user.email

    response = client.post("/accounts/signup/", signup_payload)

    assert response.status_code == HTTPStatus.OK
    assert response.context["form"].has_error("email", "unique")


@pytest.mark.django_db
def test_signup_shows_errors_when_form_invalid(
    client: Client, signup_payload: dict[str, str]
) -> None:
    signup_payload["password2"] = "different-placeholder"

    response = client.post("/accounts/signup/", signup_payload)

    assert response.status_code == HTTPStatus.OK
    assert response.context["form"].has_error("password2", "password_mismatch")
    assert not User.objects.exists()


@pytest.mark.django_db
def test_signup_shows_error_when_email_too_long(
    client: Client, signup_payload: dict[str, str]
) -> None:
    signup_payload["email"] = "a" * 64 + "@" + ".".join(["b" * 60] * 4) + ".com"

    response = client.post("/accounts/signup/", signup_payload)

    assert response.status_code == HTTPStatus.OK
    assert response.context["form"].has_error("email", "max_length")


def test_signup_page_redirects_when_already_logged_in(client: Client, consumer_user: User) -> None:
    client.force_login(consumer_user)

    response = client.get("/accounts/signup/")

    assert response.status_code == HTTPStatus.FOUND
    assert response["Location"] == "/"


@pytest.mark.django_db
def test_signup_done_page_asks_to_check_email(client: Client) -> None:
    response = client.get("/accounts/signup/done/")

    assertContains(response, "Check your email")
    assertContains(response, 'href="/accounts/verify/resend/"')
