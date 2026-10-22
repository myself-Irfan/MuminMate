from datetime import timedelta
from unittest.mock import Mock

import pytest
from django.utils import timezone
from pytest_django import DjangoAssertNumQueries, Settings

from users.enums import ThrottleScope
from users.limits import LoginLimits
from users.models import ThrottleEvent
from users.services.login_failure_service import LoginFailureService
from users.throttling import digest_email, mask_ip

pytestmark = [pytest.mark.django_db, pytest.mark.usefixtures("login_limits")]


def add_failures(
    count: int,
    *,
    email: str,
    ip: str | None,
    seconds_ago: int = 0,
    scope: ThrottleScope = ThrottleScope.LOGIN_FAILURE,
) -> None:
    created_at = timezone.now() - timedelta(seconds=seconds_ago)
    ThrottleEvent.objects.bulk_create(
        ThrottleEvent(
            scope=scope,
            email_digest=digest_email(email),
            ip=ip,
            created_at=created_at,
        )
        for _ in range(count)
    )


def is_refused(email: str, ip: str | None) -> bool:
    return LoginFailureService().record_attempt(email, ip) is None


def test_record_attempt_stores_scope_digest_and_masked_ip() -> None:
    attempt = LoginFailureService().record_attempt("IRFAN@example.com", "2001:db8:1:2::9")

    assert attempt == ThrottleEvent.objects.get()
    assert attempt.scope == ThrottleScope.LOGIN_FAILURE
    assert attempt.email_digest == digest_email("irfan@example.com")
    assert attempt.ip == "2001:db8:1:2::"


def test_record_attempt_stores_null_ip_when_unknown() -> None:
    LoginFailureService().record_attempt("irfan@example.com", None)

    assert ThrottleEvent.objects.get().ip is None


@pytest.mark.parametrize(("count", "refused"), [(1, False), (2, True)])
def test_record_attempt_refused_when_email_ip_limit_reached(count: int, refused: bool) -> None:
    add_failures(count, email="irfan@example.com", ip="203.0.113.7")

    assert is_refused("IRFAN@example.com", "203.0.113.7") is refused


def test_record_attempt_allowed_when_failures_outside_window() -> None:
    add_failures(2, email="irfan@example.com", ip="203.0.113.7", seconds_ago=61)

    assert not is_refused("irfan@example.com", "203.0.113.7")


def test_record_attempt_allowed_when_email_failures_from_other_ip() -> None:
    add_failures(2, email="irfan@example.com", ip="198.51.100.1")

    assert not is_refused("irfan@example.com", "203.0.113.7")


@pytest.mark.parametrize(("count", "refused"), [(2, False), (3, True)])
def test_record_attempt_refused_when_ip_limit_reached_across_emails(
    count: int, refused: bool
) -> None:
    for n in range(count):
        add_failures(1, email=f"user{n}@example.com", ip="203.0.113.7")

    assert is_refused("irfan@example.com", "203.0.113.7") is refused


def test_record_attempt_refused_when_ipv6_failures_in_same_64() -> None:
    add_failures(2, email="irfan@example.com", ip=mask_ip("2001:db8:1:2::1"))

    assert is_refused("irfan@example.com", "2001:db8:1:2::9")


@pytest.mark.parametrize(
    ("seconds_since_last", "refused"),
    [(29, True), (31, False)],
    ids=["within_backoff", "backoff_elapsed"],
)
def test_record_attempt_refused_when_email_limit_reached(
    seconds_since_last: int, refused: bool
) -> None:
    for host in range(1, 5):
        add_failures(
            1, email="irfan@example.com", ip=f"198.51.100.{host}", seconds_ago=seconds_since_last
        )

    assert is_refused("irfan@example.com", "203.0.113.7") is refused


def test_record_attempt_ignores_ip_rules_when_ip_unknown() -> None:
    add_failures(3, email="irfan@example.com", ip=None)

    assert not is_refused("irfan@example.com", None)


def test_record_attempt_applies_email_rule_when_ip_unknown() -> None:
    add_failures(4, email="irfan@example.com", ip=None)

    assert is_refused("irfan@example.com", None)


@pytest.mark.parametrize("scope", [ThrottleScope.PASSWORD_RESET, ThrottleScope.SIGNUP])
def test_record_attempt_ignores_other_scopes(scope: ThrottleScope) -> None:
    add_failures(4, email="irfan@example.com", ip="203.0.113.7", scope=scope)

    assert not is_refused("irfan@example.com", "203.0.113.7")


def test_record_attempt_refusal_not_kept() -> None:
    add_failures(2, email="irfan@example.com", ip="203.0.113.7")

    is_refused("irfan@example.com", "203.0.113.7")

    assert ThrottleEvent.objects.count() == 2


# A parallel attempt's row lands right after ours: counting before inserting would miss it.
def test_record_attempt_refused_when_parallel_attempt_lands_before_count(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    add_failures(1, email="irfan@example.com", ip="203.0.113.7")
    create = ThrottleEvent.objects.create
    monkeypatch.setattr(
        ThrottleEvent.objects,
        "create",
        Mock(side_effect=lambda **fields: [create(**fields), create(**fields)][0]),
    )

    assert is_refused("irfan@example.com", "203.0.113.7")


def test_record_attempt_inserts_and_counts_in_two_queries(
    django_assert_num_queries: DjangoAssertNumQueries,
) -> None:
    with django_assert_num_queries(2):
        LoginFailureService().record_attempt("irfan@example.com", "203.0.113.7")


def test_clear_attempt_deletes_attempt_and_pair_failures() -> None:
    add_failures(1, email="irfan@example.com", ip="203.0.113.7")
    add_failures(1, email="irfan@example.com", ip="198.51.100.1")
    attempt = LoginFailureService().record_attempt("irfan@example.com", "203.0.113.7")
    assert attempt is not None

    LoginFailureService().clear_attempt(attempt)

    assert list(ThrottleEvent.objects.values_list("ip", flat=True)) == ["198.51.100.1"]


def test_clear_attempt_deletes_only_attempt_when_ip_unknown() -> None:
    add_failures(1, email="irfan@example.com", ip=None)
    attempt = LoginFailureService().record_attempt("irfan@example.com", None)
    assert attempt is not None

    LoginFailureService().clear_attempt(attempt)

    assert ThrottleEvent.objects.count() == 1


def test_clear_attempt_keeps_other_scopes() -> None:
    add_failures(1, email="irfan@example.com", ip="203.0.113.7", scope=ThrottleScope.PASSWORD_RESET)
    attempt = LoginFailureService().record_attempt("irfan@example.com", "203.0.113.7")
    assert attempt is not None

    LoginFailureService().clear_attempt(attempt)

    assert list(ThrottleEvent.objects.values_list("scope", flat=True)) == [
        ThrottleScope.PASSWORD_RESET
    ]


def test_clear_deletes_only_email_ip_pair() -> None:
    LoginFailureService().record_attempt("irfan@example.com", "2001:db8:1:2::1")
    LoginFailureService().record_attempt("irfan@example.com", "198.51.100.1")
    LoginFailureService().record_attempt("other@example.com", "2001:db8:1:2::1")

    LoginFailureService().clear("irfan@example.com", "2001:db8:1:2::9")

    remaining = set(ThrottleEvent.objects.values_list("email_digest", "ip"))
    assert remaining == {
        (digest_email("irfan@example.com"), "198.51.100.1"),
        (digest_email("other@example.com"), "2001:db8:1:2::"),
    }


def test_clear_keeps_other_scopes() -> None:
    add_failures(1, email="irfan@example.com", ip="203.0.113.7", scope=ThrottleScope.PASSWORD_RESET)
    LoginFailureService().record_attempt("irfan@example.com", "203.0.113.7")

    LoginFailureService().clear("irfan@example.com", "203.0.113.7")

    assert list(ThrottleEvent.objects.values_list("scope", flat=True)) == [
        ThrottleScope.PASSWORD_RESET
    ]


def test_clear_keeps_rows_when_ip_unknown() -> None:
    LoginFailureService().record_attempt("irfan@example.com", None)

    LoginFailureService().clear("irfan@example.com", None)

    assert ThrottleEvent.objects.count() == 1


def test_delete_expired_keeps_rows_within_longest_window() -> None:
    now = timezone.now()
    login = ThrottleScope.LOGIN_FAILURE
    ThrottleEvent.objects.create(
        scope=login, email_digest="old", created_at=now - timedelta(seconds=301)
    )
    kept = ThrottleEvent.objects.create(
        scope=login, email_digest="new", created_at=now - timedelta(seconds=299)
    )

    deleted = LoginFailureService().delete_expired()

    assert deleted == 1
    assert list(ThrottleEvent.objects.values_list("id", flat=True)) == [kept.id]


@pytest.mark.parametrize("rule", ["email_ip", "ip", "email"])
def test_delete_expired_keeps_rows_within_any_rule_window(
    settings: Settings, login_limits: LoginLimits, rule: str
) -> None:
    login = login_limits.model_copy(update={f"{rule}_window_seconds": 600})
    settings.THROTTLE_LIMITS = settings.THROTTLE_LIMITS.model_copy(update={"login": login})
    ThrottleEvent.objects.create(
        scope=ThrottleScope.LOGIN_FAILURE,
        email_digest="recent",
        created_at=timezone.now() - timedelta(seconds=400),
    )

    deleted = LoginFailureService().delete_expired()

    assert deleted == 0


def test_delete_expired_keeps_other_scopes() -> None:
    add_failures(
        1, email="irfan@example.com", ip=None, seconds_ago=301, scope=ThrottleScope.PASSWORD_RESET
    )

    deleted = LoginFailureService().delete_expired()

    assert deleted == 0
    assert ThrottleEvent.objects.count() == 1
