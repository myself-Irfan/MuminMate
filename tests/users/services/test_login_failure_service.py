from datetime import timedelta

import pytest
from django.utils import timezone
from pytest_django import DjangoAssertNumQueries, Settings

from users.limits import LoginLimits
from users.models import LoginFailure
from users.services.login_failure_service import LoginFailureService
from users.throttling import digest_email, mask_ip


def add_failures(count: int, *, email: str, ip: str | None, seconds_ago: int = 0) -> None:
    failed_at = timezone.now() - timedelta(seconds=seconds_ago)
    LoginFailure.objects.bulk_create(
        LoginFailure(email_digest=digest_email(email), ip=ip, failed_at=failed_at)
        for _ in range(count)
    )


@pytest.mark.django_db
@pytest.mark.usefixtures("login_limits")
def test_is_throttled_false_when_no_failures() -> None:
    assert not LoginFailureService().is_throttled("irfan@example.com", "203.0.113.7")


@pytest.mark.django_db
@pytest.mark.usefixtures("login_limits")
@pytest.mark.parametrize(("count", "throttled"), [(1, False), (2, True)])
def test_is_throttled_when_email_ip_limit_reached(count: int, throttled: bool) -> None:
    add_failures(count, email="irfan@example.com", ip="203.0.113.7")

    assert LoginFailureService().is_throttled("IRFAN@example.com", "203.0.113.7") is throttled


@pytest.mark.django_db
@pytest.mark.usefixtures("login_limits")
def test_is_throttled_false_when_failures_outside_window() -> None:
    add_failures(2, email="irfan@example.com", ip="203.0.113.7", seconds_ago=61)

    assert not LoginFailureService().is_throttled("irfan@example.com", "203.0.113.7")


@pytest.mark.django_db
@pytest.mark.usefixtures("login_limits")
def test_is_throttled_false_when_email_failures_from_other_ip() -> None:
    add_failures(2, email="irfan@example.com", ip="198.51.100.1")

    assert not LoginFailureService().is_throttled("irfan@example.com", "203.0.113.7")


@pytest.mark.django_db
@pytest.mark.usefixtures("login_limits")
def test_is_throttled_when_ip_limit_reached_across_emails() -> None:
    add_failures(1, email="a@example.com", ip="203.0.113.7")
    add_failures(1, email="b@example.com", ip="203.0.113.7")
    add_failures(1, email="c@example.com", ip="203.0.113.7")

    assert LoginFailureService().is_throttled("irfan@example.com", "203.0.113.7")


@pytest.mark.django_db
@pytest.mark.usefixtures("login_limits")
def test_is_throttled_when_ipv6_failures_in_same_64() -> None:
    add_failures(2, email="irfan@example.com", ip=mask_ip("2001:db8:1:2::1"))

    assert LoginFailureService().is_throttled("irfan@example.com", "2001:db8:1:2::9")


@pytest.mark.django_db
@pytest.mark.usefixtures("login_limits")
@pytest.mark.parametrize(
    ("seconds_since_last", "throttled"),
    [(29, True), (31, False)],
    ids=["within_backoff", "backoff_elapsed"],
)
def test_is_throttled_when_email_limit_reached(seconds_since_last: int, throttled: bool) -> None:
    for host in range(1, 5):
        add_failures(
            1, email="irfan@example.com", ip=f"198.51.100.{host}", seconds_ago=seconds_since_last
        )

    assert LoginFailureService().is_throttled("irfan@example.com", "203.0.113.7") is throttled


@pytest.mark.django_db
@pytest.mark.usefixtures("login_limits")
def test_is_throttled_ignores_ip_rules_when_ip_unknown() -> None:
    add_failures(3, email="irfan@example.com", ip=None)

    assert not LoginFailureService().is_throttled("irfan@example.com", None)


@pytest.mark.django_db
@pytest.mark.usefixtures("login_limits")
def test_is_throttled_applies_email_rule_when_ip_unknown() -> None:
    add_failures(4, email="irfan@example.com", ip=None)

    assert LoginFailureService().is_throttled("irfan@example.com", None)


@pytest.mark.django_db
@pytest.mark.usefixtures("login_limits")
def test_is_throttled_checks_every_rule_in_one_query(
    django_assert_num_queries: DjangoAssertNumQueries,
) -> None:
    with django_assert_num_queries(1):
        LoginFailureService().is_throttled("irfan@example.com", "203.0.113.7")


@pytest.mark.django_db
def test_record_stores_digest_and_masked_ip() -> None:
    LoginFailureService().record("IRFAN@example.com", "2001:db8:1:2::9")

    failure = LoginFailure.objects.get()
    assert failure.email_digest == digest_email("irfan@example.com")
    assert failure.ip == "2001:db8:1:2::"


@pytest.mark.django_db
def test_record_stores_null_ip_when_unknown() -> None:
    LoginFailureService().record("irfan@example.com", None)

    assert LoginFailure.objects.get().ip is None


@pytest.mark.django_db
def test_clear_deletes_only_email_ip_pair() -> None:
    LoginFailureService().record("irfan@example.com", "2001:db8:1:2::1")
    LoginFailureService().record("irfan@example.com", "198.51.100.1")
    LoginFailureService().record("other@example.com", "2001:db8:1:2::1")

    LoginFailureService().clear("irfan@example.com", "2001:db8:1:2::9")

    remaining = set(LoginFailure.objects.values_list("email_digest", "ip"))
    assert remaining == {
        (digest_email("irfan@example.com"), "198.51.100.1"),
        (digest_email("other@example.com"), "2001:db8:1:2::"),
    }


@pytest.mark.django_db
def test_clear_keeps_rows_when_ip_unknown() -> None:
    LoginFailureService().record("irfan@example.com", None)

    LoginFailureService().clear("irfan@example.com", None)

    assert LoginFailure.objects.count() == 1


@pytest.mark.django_db
@pytest.mark.usefixtures("login_limits")
def test_delete_expired_keeps_rows_within_longest_window() -> None:
    now = timezone.now()
    LoginFailure.objects.create(email_digest="old", failed_at=now - timedelta(seconds=301))
    kept = LoginFailure.objects.create(email_digest="new", failed_at=now - timedelta(seconds=299))

    deleted = LoginFailureService().delete_expired()

    assert deleted == 1
    assert list(LoginFailure.objects.values_list("id", flat=True)) == [kept.id]


@pytest.mark.django_db
@pytest.mark.parametrize("rule", ["email_ip", "ip", "email"])
def test_delete_expired_keeps_rows_within_any_rule_window(
    settings: Settings, login_limits: LoginLimits, rule: str
) -> None:
    longest = getattr(login_limits, rule).model_copy(update={"window_seconds": 600})
    settings.LOGIN_LIMITS = login_limits.model_copy(update={rule: longest})
    LoginFailure.objects.create(
        email_digest="recent", failed_at=timezone.now() - timedelta(seconds=400)
    )

    deleted = LoginFailureService().delete_expired()

    assert deleted == 0
