from http import HTTPStatus
from unittest.mock import Mock

import pytest
from django.contrib.auth import SESSION_KEY
from django.test import Client
from pytest_django import DjangoCaptureOnCommitCallbacks
from pytest_django.asserts import assertContains, assertTemplateUsed

from users.enums import ThrottleScope
from users.models import ThrottleEvent, User


@pytest.fixture
def new_password() -> str:
    return "fresh-placeholder-passphrase"


@pytest.fixture
def password_payload(password: str, new_password: str) -> dict[str, str]:
    return {
        "row": "password",
        "old_password": password,
        "new_password1": new_password,
        "new_password2": new_password,
    }


def test_settings_page_shows_password_row(consumer_client: Client) -> None:
    response = consumer_client.get("/accounts/settings/")

    assert response.status_code == HTTPStatus.OK
    assertTemplateUsed(response, "users/account_settings.html")
    assertContains(response, 'name="old_password"')


def test_settings_page_links_to_profile_tab(consumer_client: Client) -> None:
    response = consumer_client.get("/accounts/settings/")

    assertContains(response, '<a href="/accounts/profile/">Profile</a>', html=True)
    assertContains(
        response, '<a href="/accounts/settings/" aria-current="page">Settings</a>', html=True
    )


def test_profile_page_links_to_settings_tab(consumer_client: Client) -> None:
    response = consumer_client.get("/accounts/profile/")

    assertContains(response, '<a href="/accounts/settings/">Settings</a>', html=True)


def test_password_change_saves_and_keeps_this_session(
    consumer_client: Client,
    consumer_user: User,
    password_payload: dict[str, str],
    new_password: str,
) -> None:
    response = consumer_client.post("/accounts/settings/", password_payload, follow=True)

    assert response.redirect_chain == [("/accounts/settings/", HTTPStatus.FOUND)]
    assertContains(response, "Your password is changed.")
    consumer_user.refresh_from_db()
    assert consumer_user.check_password(new_password)
    assert consumer_client.session[SESSION_KEY] == str(consumer_user.pk)


def test_password_change_queues_changed_email(
    django_capture_on_commit_callbacks: DjangoCaptureOnCommitCallbacks,
    password_changed_email_delay: Mock,
    consumer_client: Client,
    consumer_user: User,
    password_payload: dict[str, str],
) -> None:
    with django_capture_on_commit_callbacks(execute=True):
        consumer_client.post("/accounts/settings/", password_payload)

    password_changed_email_delay.assert_called_once_with(consumer_user.pk)


def test_password_change_queues_no_email_when_old_password_wrong(
    django_capture_on_commit_callbacks: DjangoCaptureOnCommitCallbacks,
    password_changed_email_delay: Mock,
    consumer_client: Client,
    password_payload: dict[str, str],
) -> None:
    with django_capture_on_commit_callbacks(execute=True):
        consumer_client.post(
            "/accounts/settings/",
            {**password_payload, "old_password": "wrong-placeholder-password"},
        )

    password_changed_email_delay.assert_not_called()


def test_password_change_logs_out_other_sessions(
    consumer_client: Client, consumer_user: User, password_payload: dict[str, str]
) -> None:
    other_device = Client()
    other_device.force_login(consumer_user)

    consumer_client.post("/accounts/settings/", password_payload)

    response = other_device.get("/accounts/settings/")
    assert response["Location"] == "/accounts/login/?next=/accounts/settings/"


def test_password_change_shows_error_with_row_open_when_old_password_wrong(
    consumer_client: Client, consumer_user: User, password_payload: dict[str, str], password: str
) -> None:
    response = consumer_client.post(
        "/accounts/settings/", {**password_payload, "old_password": "wrong-placeholder-password"}
    )

    assert response.status_code == HTTPStatus.OK
    assert response.context["open_row"] == "password"
    assert response.context["forms"]["password"].has_error("old_password", "password_incorrect")
    consumer_user.refresh_from_db()
    assert consumer_user.check_password(password)


@pytest.fixture
def wrong_password_payload(password_payload: dict[str, str]) -> dict[str, str]:
    return {**password_payload, "old_password": "wrong-placeholder-password"}


def add_wrong_passwords(count: int, user: User) -> None:
    ThrottleEvent.objects.bulk_create(
        ThrottleEvent(scope=ThrottleScope.CURRENT_PASSWORD_FAILURE, user=user) for _ in range(count)
    )


@pytest.mark.usefixtures("request_limits")
def test_password_change_counts_wrong_password_and_keeps_session_under_limit(
    consumer_client: Client, consumer_user: User, wrong_password_payload: dict[str, str]
) -> None:
    add_wrong_passwords(2, consumer_user)

    response = consumer_client.post("/accounts/settings/", wrong_password_payload)

    assert response.status_code == HTTPStatus.OK
    assert consumer_client.session[SESSION_KEY] == str(consumer_user.pk)
    assert ThrottleEvent.objects.filter(user=consumer_user).count() == 3


@pytest.mark.usefixtures("request_limits")
def test_password_change_logs_out_when_wrong_password_limit_reached(
    consumer_client: Client, consumer_user: User, password_payload: dict[str, str], password: str
) -> None:
    add_wrong_passwords(3, consumer_user)

    response = consumer_client.post("/accounts/settings/", password_payload, follow=True)

    assert response.redirect_chain == [("/accounts/login/", HTTPStatus.FOUND)]
    assertContains(
        response,
        "Too many wrong passwords. Log in again; to change your email or password today,"
        " reset your password first.",
    )
    assert SESSION_KEY not in consumer_client.session
    consumer_user.refresh_from_db()
    assert consumer_user.check_password(password)


@pytest.mark.parametrize(
    "changes",
    [{}, {"new_password2": "other-placeholder-passphrase"}],
    ids=["saved", "new_passwords_differ"],
)
@pytest.mark.usefixtures("request_limits")
def test_password_change_counts_nothing_when_old_password_correct(
    consumer_client: Client, password_payload: dict[str, str], changes: dict[str, str]
) -> None:
    consumer_client.post("/accounts/settings/", {**password_payload, **changes})

    assert not ThrottleEvent.objects.exists()


@pytest.fixture
def email_payload(password: str) -> dict[str, str]:
    return {"row": "email", "email": "new@example.com", "current_password": password}


def test_settings_page_shows_email_row_with_current_email(consumer_client: Client) -> None:
    response = consumer_client.get("/accounts/settings/")

    assertContains(response, '<span class="row-value">irfan@example.com</span>', html=True)
    assertContains(response, 'name="current_password"')


@pytest.mark.usefixtures("request_limits")
def test_email_change_sends_link_and_keeps_email_until_confirmed(
    django_capture_on_commit_callbacks: DjangoCaptureOnCommitCallbacks,
    email_change_link_delay: Mock,
    consumer_client: Client,
    consumer_user: User,
    email_payload: dict[str, str],
) -> None:
    with django_capture_on_commit_callbacks(execute=True):
        response = consumer_client.post("/accounts/settings/", email_payload, follow=True)

    assert response.redirect_chain == [("/accounts/settings/", HTTPStatus.FOUND)]
    assertContains(response, "We sent a link to new@example.com. Open it to finish the change.")
    email_change_link_delay.assert_called_once_with(consumer_user.pk, "new@example.com")
    consumer_user.refresh_from_db()
    assert consumer_user.email == "irfan@example.com"


@pytest.mark.usefixtures("request_limits")
def test_email_change_counts_wrong_password_and_shows_error_with_row_open(
    email_change_link_delay: Mock,
    consumer_client: Client,
    consumer_user: User,
    email_payload: dict[str, str],
) -> None:
    response = consumer_client.post(
        "/accounts/settings/", {**email_payload, "current_password": "wrong-placeholder-password"}
    )

    assert response.status_code == HTTPStatus.OK
    assert response.context["open_row"] == "email"
    assert response.context["forms"]["email"].has_error("current_password", "password_incorrect")
    assert ThrottleEvent.objects.filter(
        scope=ThrottleScope.CURRENT_PASSWORD_FAILURE, user=consumer_user
    ).exists()
    email_change_link_delay.assert_not_called()


@pytest.mark.parametrize(
    ("email", "code"),
    [("staff@example.com", "unique"), ("irfan@example.com", "email_unchanged")],
    ids=["taken", "unchanged"],
)
@pytest.mark.usefixtures("request_limits", "staff_user")
def test_email_change_shows_error_and_counts_nothing_when_email_refused(
    email_change_link_delay: Mock,
    consumer_client: Client,
    email_payload: dict[str, str],
    email: str,
    code: str,
) -> None:
    response = consumer_client.post("/accounts/settings/", {**email_payload, "email": email})

    assert response.context["forms"]["email"].has_error("email", code)
    assert not ThrottleEvent.objects.exists()
    email_change_link_delay.assert_not_called()


@pytest.mark.usefixtures("request_limits")
def test_email_change_logs_out_when_wrong_password_limit_reached(
    consumer_client: Client, consumer_user: User, email_payload: dict[str, str]
) -> None:
    add_wrong_passwords(3, consumer_user)

    response = consumer_client.post("/accounts/settings/", email_payload, follow=True)

    assert response.redirect_chain == [("/accounts/login/", HTTPStatus.FOUND)]
    assertContains(
        response,
        "Too many wrong passwords. Log in again; to change your email or password today,"
        " reset your password first.",
    )
    assert SESSION_KEY not in consumer_client.session


@pytest.mark.usefixtures("request_limits")
def test_email_change_refused_when_link_limit_reached(
    email_change_link_delay: Mock,
    consumer_client: Client,
    consumer_user: User,
    email_payload: dict[str, str],
) -> None:
    ThrottleEvent.objects.create(scope=ThrottleScope.EMAIL_CHANGE, user=consumer_user)

    response = consumer_client.post("/accounts/settings/", email_payload)

    assertContains(
        response,
        "Too many email change requests. Try again later.",
        status_code=HTTPStatus.TOO_MANY_REQUESTS,
    )
    assert response.context["open_row"] == "email"
    email_change_link_delay.assert_not_called()


def test_settings_row_refused_when_row_unknown(consumer_client: Client) -> None:
    response = consumer_client.post("/accounts/settings/", {"row": "is_staff"})

    assert response.status_code == HTTPStatus.BAD_REQUEST


@pytest.mark.django_db
def test_settings_page_redirects_to_login_when_anonymous(client: Client) -> None:
    response = client.get("/accounts/settings/")

    assert response["Location"] == "/accounts/login/?next=/accounts/settings/"


def test_settings_page_redirects_privileged_user_to_admin(client: Client, staff_user: User) -> None:
    client.force_login(staff_user)

    response = client.get("/accounts/settings/")

    assert response["Location"] == "/admin/"
