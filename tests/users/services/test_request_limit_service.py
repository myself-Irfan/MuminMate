import io
from collections.abc import Callable
from datetime import timedelta
from unittest.mock import Mock

import pytest
from django.utils import timezone

from tests.logging_support import events
from users.enums import ThrottleScope
from users.models import ThrottleEvent
from users.services.request_limit_service import RequestLimitService
from users.throttling import digest_email, mask_ip

pytestmark = [pytest.mark.django_db, pytest.mark.usefixtures("request_limits")]


def add_requests(
    count: int,
    *,
    scope: ThrottleScope,
    email: str = "irfan@example.com",
    ip: str | None = "203.0.113.7",
    seconds_ago: int = 120,
) -> None:
    created_at = timezone.now() - timedelta(seconds=seconds_ago)
    ThrottleEvent.objects.bulk_create(
        ThrottleEvent(scope=scope, email_digest=digest_email(email), ip=ip, created_at=created_at)
        for _ in range(count)
    )


def test_password_reset_recorded_when_no_requests() -> None:
    assert RequestLimitService().record_password_reset("IRFAN@example.com", "2001:db8:1:2::9")

    event = ThrottleEvent.objects.get()
    assert event.scope == ThrottleScope.PASSWORD_RESET
    assert event.email_digest == digest_email("irfan@example.com")
    assert event.ip == "2001:db8:1:2::"


@pytest.mark.parametrize(("count", "allowed"), [(2, True), (3, False)])
def test_password_reset_refused_when_email_cap_reached(count: int, allowed: bool) -> None:
    add_requests(count, scope=ThrottleScope.PASSWORD_RESET, ip="198.51.100.1")

    service = RequestLimitService()

    assert service.record_password_reset("IRFAN@example.com", "203.0.113.7") is allowed


@pytest.mark.parametrize(("seconds_ago", "allowed"), [(59, False), (61, True)])
def test_password_reset_refused_within_cooldown(seconds_ago: int, allowed: bool) -> None:
    add_requests(1, scope=ThrottleScope.PASSWORD_RESET, seconds_ago=seconds_ago)

    service = RequestLimitService()

    assert service.record_password_reset("irfan@example.com", "203.0.113.7") is allowed


def test_password_reset_allowed_when_email_requests_outside_window() -> None:
    add_requests(3, scope=ThrottleScope.PASSWORD_RESET, seconds_ago=3601)

    assert RequestLimitService().record_password_reset("irfan@example.com", "203.0.113.7")


@pytest.mark.parametrize(("count", "allowed"), [(4, True), (5, False)])
def test_password_reset_refused_when_ip_cap_reached_across_emails(
    count: int, allowed: bool
) -> None:
    for n in range(count):
        add_requests(1, scope=ThrottleScope.PASSWORD_RESET, email=f"user{n}@example.com")

    service = RequestLimitService()

    assert service.record_password_reset("irfan@example.com", "203.0.113.7") is allowed


def test_password_reset_allowed_when_ip_requests_outside_window() -> None:
    for n in range(5):
        add_requests(
            1, scope=ThrottleScope.PASSWORD_RESET, email=f"user{n}@example.com", seconds_ago=1801
        )

    assert RequestLimitService().record_password_reset("irfan@example.com", "203.0.113.7")


def test_password_reset_refused_when_ipv6_requests_in_same_64() -> None:
    for n in range(5):
        add_requests(
            1,
            scope=ThrottleScope.PASSWORD_RESET,
            email=f"user{n}@example.com",
            ip=mask_ip("2001:db8:1:2::1"),
        )

    assert not RequestLimitService().record_password_reset("irfan@example.com", "2001:db8:1:2::9")


def test_password_reset_allowed_when_ip_unknown() -> None:
    add_requests(5, scope=ThrottleScope.PASSWORD_RESET, email="other@example.com", ip=None)

    assert RequestLimitService().record_password_reset("irfan@example.com", None)


def test_password_reset_applies_email_rules_when_ip_unknown() -> None:
    add_requests(1, scope=ThrottleScope.PASSWORD_RESET, ip=None, seconds_ago=30)

    assert not RequestLimitService().record_password_reset("irfan@example.com", None)


@pytest.mark.parametrize("scope", [ThrottleScope.LOGIN_FAILURE, ThrottleScope.SIGNUP])
def test_password_reset_ignores_other_scopes(scope: ThrottleScope) -> None:
    add_requests(5, scope=scope, seconds_ago=30)

    assert RequestLimitService().record_password_reset("irfan@example.com", "203.0.113.7")


def test_password_reset_refusal_not_kept() -> None:
    add_requests(3, scope=ThrottleScope.PASSWORD_RESET)

    RequestLimitService().record_password_reset("irfan@example.com", "203.0.113.7")

    assert ThrottleEvent.objects.count() == 3


def test_password_reset_refusal_logs_scope(json_logs: io.StringIO) -> None:
    add_requests(1, scope=ThrottleScope.PASSWORD_RESET, seconds_ago=30)

    RequestLimitService().record_password_reset("irfan@example.com", "203.0.113.7")

    [line] = events(json_logs, "request_limited")
    assert line["scope"] == ThrottleScope.PASSWORD_RESET


# The signup rule reads only the IP, so no typed address is kept.
def test_signup_recorded_without_email() -> None:
    assert RequestLimitService().record_signup("203.0.113.7")

    event = ThrottleEvent.objects.get()
    assert (event.scope, event.email_digest, event.ip) == (ThrottleScope.SIGNUP, "", "203.0.113.7")


@pytest.mark.parametrize(("count", "allowed"), [(1, True), (2, False)])
def test_signup_refused_when_ip_cap_reached(count: int, allowed: bool) -> None:
    add_requests(count, scope=ThrottleScope.SIGNUP)

    assert RequestLimitService().record_signup("203.0.113.7") is allowed


def test_signup_allowed_when_requests_outside_window() -> None:
    add_requests(2, scope=ThrottleScope.SIGNUP, seconds_ago=601)

    assert RequestLimitService().record_signup("203.0.113.7")


def test_signup_allowed_from_other_ip() -> None:
    add_requests(2, scope=ThrottleScope.SIGNUP, ip="198.51.100.1")

    assert RequestLimitService().record_signup("203.0.113.7")


@pytest.mark.parametrize("scope", [ThrottleScope.LOGIN_FAILURE, ThrottleScope.PASSWORD_RESET])
def test_signup_ignores_other_scopes(scope: ThrottleScope) -> None:
    add_requests(2, scope=scope)

    assert RequestLimitService().record_signup("203.0.113.7")


# No email and no IP: no rule could ever count the row.
def test_signup_allowed_and_not_recorded_when_ip_unknown() -> None:
    assert RequestLimitService().record_signup(None)

    assert not ThrottleEvent.objects.exists()


# A parallel request's row lands right after ours: counting before inserting would miss it.
@pytest.mark.parametrize(
    "record",
    [
        lambda service: service.record_password_reset("irfan@example.com", "203.0.113.7"),
        lambda service: service.record_signup("203.0.113.7"),
        lambda service: service.record_verification_email("irfan@example.com"),
    ],
    ids=["password_reset", "signup", "verification_email"],
)
def test_record_refused_when_parallel_request_lands_before_count(
    monkeypatch: pytest.MonkeyPatch, record: Callable[[RequestLimitService], bool]
) -> None:
    # With the parallel row, signup reaches its cap of 2; the others refuse by cooldown.
    add_requests(1, scope=ThrottleScope.SIGNUP)
    create = ThrottleEvent.objects.create
    monkeypatch.setattr(
        ThrottleEvent.objects,
        "create",
        Mock(side_effect=lambda **fields: [create(**fields), create(**fields)][0]),
    )

    assert not record(RequestLimitService())


def test_signup_refusal_not_kept() -> None:
    add_requests(2, scope=ThrottleScope.SIGNUP)

    RequestLimitService().record_signup("203.0.113.7")

    assert ThrottleEvent.objects.count() == 2


def test_signup_refusal_logs_scope(json_logs: io.StringIO) -> None:
    add_requests(2, scope=ThrottleScope.SIGNUP)

    RequestLimitService().record_signup("203.0.113.7")

    [line] = events(json_logs, "request_limited")
    assert line["scope"] == ThrottleScope.SIGNUP


def test_verification_email_recorded_without_ip() -> None:
    assert RequestLimitService().record_verification_email("IRFAN@example.com")

    event = ThrottleEvent.objects.get()
    assert event.scope == ThrottleScope.VERIFICATION_EMAIL
    assert event.email_digest == digest_email("irfan@example.com")
    assert event.ip is None


@pytest.mark.parametrize(("count", "allowed"), [(2, True), (3, False)])
def test_verification_email_refused_when_email_cap_reached(count: int, allowed: bool) -> None:
    add_requests(count, scope=ThrottleScope.VERIFICATION_EMAIL, ip=None)

    assert RequestLimitService().record_verification_email("IRFAN@example.com") is allowed


@pytest.mark.parametrize(("seconds_ago", "allowed"), [(59, False), (61, True)])
def test_verification_email_refused_within_cooldown(seconds_ago: int, allowed: bool) -> None:
    add_requests(1, scope=ThrottleScope.VERIFICATION_EMAIL, ip=None, seconds_ago=seconds_ago)

    assert RequestLimitService().record_verification_email("irfan@example.com") is allowed


def test_verification_email_allowed_when_requests_outside_window() -> None:
    add_requests(3, scope=ThrottleScope.VERIFICATION_EMAIL, ip=None, seconds_ago=3601)

    assert RequestLimitService().record_verification_email("irfan@example.com")


def test_verification_email_allowed_for_other_email() -> None:
    add_requests(3, scope=ThrottleScope.VERIFICATION_EMAIL, email="other@example.com", ip=None)

    assert RequestLimitService().record_verification_email("irfan@example.com")


@pytest.mark.parametrize("scope", [ThrottleScope.LOGIN_FAILURE, ThrottleScope.PASSWORD_RESET])
def test_verification_email_ignores_other_scopes(scope: ThrottleScope) -> None:
    add_requests(3, scope=scope, seconds_ago=30)

    assert RequestLimitService().record_verification_email("irfan@example.com")


def test_verification_email_refusal_not_kept() -> None:
    add_requests(3, scope=ThrottleScope.VERIFICATION_EMAIL, ip=None)

    RequestLimitService().record_verification_email("irfan@example.com")

    assert ThrottleEvent.objects.count() == 3


def test_verification_email_refusal_logs_scope(json_logs: io.StringIO) -> None:
    add_requests(1, scope=ThrottleScope.VERIFICATION_EMAIL, ip=None, seconds_ago=30)

    RequestLimitService().record_verification_email("irfan@example.com")

    [line] = events(json_logs, "request_limited")
    assert line["scope"] == ThrottleScope.VERIFICATION_EMAIL


def test_record_stores_scope_digest_and_masked_ip() -> None:
    event = RequestLimitService().record(
        ThrottleScope.PASSWORD_RESET, "IRFAN@example.com", "2001:db8:1:2::9"
    )

    assert event == ThrottleEvent.objects.get()
    assert event.scope == ThrottleScope.PASSWORD_RESET
    assert event.email_digest == digest_email("irfan@example.com")
    assert event.ip == "2001:db8:1:2::"


def test_record_stores_null_ip_when_unknown() -> None:
    RequestLimitService().record(ThrottleScope.SIGNUP, "irfan@example.com", None)

    assert ThrottleEvent.objects.get().ip is None


@pytest.mark.parametrize(
    ("scope", "longest_window"),
    [
        (ThrottleScope.PASSWORD_RESET, 3600),
        (ThrottleScope.SIGNUP, 600),
        (ThrottleScope.VERIFICATION_EMAIL, 3600),
    ],
)
def test_delete_expired_keeps_rows_within_scope_longest_window(
    scope: ThrottleScope, longest_window: int
) -> None:
    add_requests(1, scope=scope, seconds_ago=longest_window + 1)
    add_requests(1, scope=scope, seconds_ago=longest_window - 1)

    deleted = RequestLimitService().delete_expired()

    assert deleted == 1
    assert ThrottleEvent.objects.count() == 1


def test_delete_expired_keeps_login_failures() -> None:
    add_requests(1, scope=ThrottleScope.LOGIN_FAILURE, seconds_ago=86400)

    deleted = RequestLimitService().delete_expired()

    assert deleted == 0
