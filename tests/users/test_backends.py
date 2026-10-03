from unittest.mock import Mock

import pytest
from asgiref.sync import async_to_sync
from django.contrib.auth import SESSION_KEY, aauthenticate, authenticate
from django.test import Client, RequestFactory

from users.models import LoginFailure, User
from users.services.login_failure_service import LoginFailureService

pytestmark = pytest.mark.usefixtures("login_limits")


def test_authenticate_returns_user_and_clears_pair_failures(
    rf: RequestFactory, consumer_user: User, password: str
) -> None:
    LoginFailureService().record(consumer_user.email, "127.0.0.1")

    user = authenticate(rf.post("/"), username=consumer_user.email, password=password)

    assert user == consumer_user
    assert not LoginFailure.objects.exists()


def test_authenticate_records_failure_when_password_wrong(
    rf: RequestFactory, consumer_user: User, password: str
) -> None:
    user = authenticate(rf.post("/"), username=consumer_user.email, password=password + "-wrong")

    assert user is None
    assert LoginFailure.objects.get().ip == "127.0.0.1"


@pytest.mark.django_db
def test_authenticate_records_failure_when_email_unknown(rf: RequestFactory, password: str) -> None:
    user = authenticate(rf.post("/"), username="nobody@example.com", password=password)

    assert user is None
    assert LoginFailure.objects.count() == 1


@pytest.mark.django_db
def test_authenticate_records_nothing_when_username_missing(
    rf: RequestFactory, password: str
) -> None:
    user = authenticate(rf.post("/"), password=password)

    assert user is None
    assert not LoginFailure.objects.exists()


@pytest.mark.django_db
def test_authenticate_records_failure_without_ip_when_no_request(password: str) -> None:
    authenticate(username="nobody@example.com", password=password)

    assert LoginFailure.objects.get().ip is None


def test_authenticate_refuses_without_checking_password_when_throttled(
    rf: RequestFactory, monkeypatch: pytest.MonkeyPatch, consumer_user: User, password: str
) -> None:
    LoginFailureService().record(consumer_user.email, "127.0.0.1")
    LoginFailureService().record(consumer_user.email, "127.0.0.1")
    check_password = Mock(return_value=True)
    monkeypatch.setattr(User, "check_password", check_password)

    user = authenticate(rf.post("/"), username=consumer_user.email, password=password)

    assert user is None
    check_password.assert_not_called()
    assert LoginFailure.objects.count() == 2


def test_aauthenticate_records_failure_when_password_wrong(
    rf: RequestFactory, consumer_user: User, password: str
) -> None:
    user = async_to_sync(aauthenticate)(
        rf.post("/"), username=consumer_user.email, password=password + "-wrong"
    )

    assert user is None
    assert LoginFailure.objects.get().ip == "127.0.0.1"


def test_aauthenticate_refuses_without_checking_password_when_throttled(
    rf: RequestFactory, monkeypatch: pytest.MonkeyPatch, consumer_user: User, password: str
) -> None:
    LoginFailureService().record(consumer_user.email, "127.0.0.1")
    LoginFailureService().record(consumer_user.email, "127.0.0.1")
    check_password = Mock(return_value=True)
    monkeypatch.setattr(User, "check_password", check_password)

    user = async_to_sync(aauthenticate)(
        rf.post("/"), username=consumer_user.email, password=password
    )

    assert user is None
    check_password.assert_not_called()
    assert LoginFailure.objects.count() == 2


def test_consumer_login_refuses_with_generic_error_when_throttled(
    client: Client, consumer_user: User, password: str
) -> None:
    LoginFailureService().record(consumer_user.email, "127.0.0.1")
    LoginFailureService().record(consumer_user.email, "127.0.0.1")

    response = client.post(
        "/accounts/login/", {"username": consumer_user.email, "password": password}
    )

    errors = response.context["form"].non_field_errors().as_data()
    assert [error.code for error in errors] == ["invalid_login"]
    assert SESSION_KEY not in client.session


def test_admin_login_refuses_when_throttled(
    client: Client, staff_user: User, password: str
) -> None:
    LoginFailureService().record(staff_user.email, "127.0.0.1")
    LoginFailureService().record(staff_user.email, "127.0.0.1")

    client.post("/admin/login/", {"username": staff_user.email, "password": password})

    assert SESSION_KEY not in client.session
