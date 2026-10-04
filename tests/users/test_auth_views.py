from http import HTTPStatus

import pytest
from django.contrib.auth import SESSION_KEY
from django.test import Client
from pytest_django.asserts import assertContains

from users.models import User


@pytest.fixture
def login_payload(consumer_user: User, password: str) -> dict[str, str]:
    return {"username": consumer_user.email, "password": password}


@pytest.fixture
def signup_payload(password: str) -> dict[str, str]:
    return {"email": "new@example.com", "password1": password, "password2": password}


@pytest.mark.django_db
def test_login_page_email_field_is_email_type(client: Client) -> None:
    response = client.get("/accounts/login/")

    assertContains(response, 'type="email" name="username"')


@pytest.mark.django_db
def test_login_page_links_staff_to_admin_login(client: Client) -> None:
    response = client.get("/accounts/login/")

    assertContains(response, 'href="/admin/login/"')


@pytest.mark.django_db
def test_login_page_links_to_signup(client: Client) -> None:
    response = client.get("/accounts/login/")

    assertContains(response, 'href="/accounts/signup/"')


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


def test_signup_answers_taken_email_like_new_one(
    client: Client, consumer_user: User, signup_payload: dict[str, str]
) -> None:
    signup_payload["email"] = consumer_user.email.upper()

    response = client.post("/accounts/signup/", signup_payload)

    assert response.status_code == HTTPStatus.FOUND
    assert response["Location"] == "/accounts/signup/done/"
    assert User.objects.count() == 1


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


def test_login_redirects_home_when_credentials_valid(
    client: Client, consumer_user: User, login_payload: dict[str, str]
) -> None:
    response = client.post("/accounts/login/", login_payload)

    assert response.status_code == HTTPStatus.FOUND
    assert response["Location"] == "/"
    assert client.session[SESSION_KEY] == str(consumer_user.pk)


def test_login_rotates_session_key(client: Client, login_payload: dict[str, str]) -> None:
    session = client.session
    session.save()
    key_before = session.session_key

    client.post("/accounts/login/", login_payload)

    assert client.session.session_key != key_before


@pytest.mark.parametrize(
    "credentials",
    [
        {"username": "irfan@example.com", "password": "wrong-placeholder-password"},
        {"username": "nobody@example.com", "password": "placeholder-password"},
        {"username": "staff@example.com", "password": "placeholder-password"},
    ],
    ids=["wrong_password", "unknown_email", "staff_account"],
)
@pytest.mark.usefixtures("consumer_user", "staff_user")
def test_login_fails_with_same_error(client: Client, credentials: dict[str, str]) -> None:
    response = client.post("/accounts/login/", credentials)

    assert response.status_code == HTTPStatus.OK
    errors = response.context["form"].non_field_errors().as_data()
    assert [error.code for error in errors] == ["invalid_login"]
    assert SESSION_KEY not in client.session


def test_login_ignores_next_on_other_host(client: Client, login_payload: dict[str, str]) -> None:
    response = client.post("/accounts/login/?next=https://evil.example/", login_payload)

    assert response["Location"] == "/"


def test_login_follows_next_on_same_host(client: Client, login_payload: dict[str, str]) -> None:
    response = client.post("/accounts/login/?next=/admin/", login_payload)

    assert response["Location"] == "/admin/"


def test_login_page_redirects_when_already_logged_in(client: Client, consumer_user: User) -> None:
    client.force_login(consumer_user)

    response = client.get("/accounts/login/")

    assert response.status_code == HTTPStatus.FOUND
    assert response["Location"] == "/"


def test_logout_rejects_get(client: Client, consumer_user: User) -> None:
    client.force_login(consumer_user)

    response = client.get("/accounts/logout/")

    assert response.status_code == HTTPStatus.METHOD_NOT_ALLOWED
    assert SESSION_KEY in client.session


def test_logout_ends_session(client: Client, consumer_user: User) -> None:
    client.force_login(consumer_user)

    response = client.post("/accounts/logout/")

    assert response.status_code == HTTPStatus.FOUND
    assert response["Location"] == "/accounts/login/"
    assert SESSION_KEY not in client.session
