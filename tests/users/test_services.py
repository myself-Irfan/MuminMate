from datetime import timedelta

import pytest
from django.utils import timezone
from pytest_django import Settings

from config.env import LoginLimits
from users.models import LoginFailure
from users.selectors import digest_email
from users.services import (
    clear_login_failures,
    delete_expired_login_failures,
    record_login_failure,
)


@pytest.mark.django_db
def test_record_login_failure_stores_digest_and_masked_ip() -> None:
    record_login_failure("IRFAN@example.com", "2001:db8:1:2::9")

    failure = LoginFailure.objects.get()
    assert failure.email_digest == digest_email("irfan@example.com")
    assert failure.ip == "2001:db8:1:2::"


@pytest.mark.django_db
def test_record_login_failure_stores_null_ip_when_unknown() -> None:
    record_login_failure("irfan@example.com", None)

    assert LoginFailure.objects.get().ip is None


@pytest.mark.django_db
def test_clear_login_failures_deletes_only_email_ip_pair() -> None:
    record_login_failure("irfan@example.com", "2001:db8:1:2::1")
    record_login_failure("irfan@example.com", "198.51.100.1")
    record_login_failure("other@example.com", "2001:db8:1:2::1")

    clear_login_failures("irfan@example.com", "2001:db8:1:2::9")

    remaining = set(LoginFailure.objects.values_list("email_digest", "ip"))
    assert remaining == {
        (digest_email("irfan@example.com"), "198.51.100.1"),
        (digest_email("other@example.com"), "2001:db8:1:2::"),
    }


@pytest.mark.django_db
def test_clear_login_failures_keeps_rows_when_ip_unknown() -> None:
    record_login_failure("irfan@example.com", None)

    clear_login_failures("irfan@example.com", None)

    assert LoginFailure.objects.count() == 1


@pytest.mark.django_db
@pytest.mark.usefixtures("login_limits")
def test_delete_expired_login_failures_keeps_rows_within_longest_window() -> None:
    now = timezone.now()
    LoginFailure.objects.create(email_digest="old", failed_at=now - timedelta(seconds=301))
    kept = LoginFailure.objects.create(email_digest="new", failed_at=now - timedelta(seconds=299))

    deleted = delete_expired_login_failures()

    assert deleted == 1
    assert list(LoginFailure.objects.values_list("id", flat=True)) == [kept.id]


@pytest.mark.django_db
@pytest.mark.parametrize("rule", ["email_ip", "ip", "email"])
def test_delete_expired_login_failures_keeps_rows_within_any_rule_window(
    settings: Settings, login_limits: LoginLimits, rule: str
) -> None:
    longest = getattr(login_limits, rule).model_copy(update={"window_seconds": 600})
    settings.LOGIN_LIMITS = login_limits.model_copy(update={rule: longest})
    LoginFailure.objects.create(
        email_digest="recent", failed_at=timezone.now() - timedelta(seconds=400)
    )

    deleted = delete_expired_login_failures()

    assert deleted == 0
