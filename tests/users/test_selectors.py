from datetime import timedelta

import pytest
from django.utils import timezone
from pytest_django import DjangoAssertNumQueries

from users.models import LoginFailure
from users.selectors import is_login_throttled
from users.throttling import digest_email, mask_ip


def add_failures(count: int, *, email: str, ip: str | None, seconds_ago: int = 0) -> None:
    failed_at = timezone.now() - timedelta(seconds=seconds_ago)
    LoginFailure.objects.bulk_create(
        LoginFailure(email_digest=digest_email(email), ip=ip, failed_at=failed_at)
        for _ in range(count)
    )


@pytest.mark.django_db
@pytest.mark.usefixtures("login_limits")
def test_is_login_throttled_false_when_no_failures() -> None:
    assert not is_login_throttled("irfan@example.com", "203.0.113.7")


@pytest.mark.django_db
@pytest.mark.usefixtures("login_limits")
@pytest.mark.parametrize(("count", "throttled"), [(1, False), (2, True)])
def test_is_login_throttled_when_email_ip_limit_reached(count: int, throttled: bool) -> None:
    add_failures(count, email="irfan@example.com", ip="203.0.113.7")

    assert is_login_throttled("IRFAN@example.com", "203.0.113.7") is throttled


@pytest.mark.django_db
@pytest.mark.usefixtures("login_limits")
def test_is_login_throttled_false_when_failures_outside_window() -> None:
    add_failures(2, email="irfan@example.com", ip="203.0.113.7", seconds_ago=61)

    assert not is_login_throttled("irfan@example.com", "203.0.113.7")


@pytest.mark.django_db
@pytest.mark.usefixtures("login_limits")
def test_is_login_throttled_false_when_email_failures_from_other_ip() -> None:
    add_failures(2, email="irfan@example.com", ip="198.51.100.1")

    assert not is_login_throttled("irfan@example.com", "203.0.113.7")


@pytest.mark.django_db
@pytest.mark.usefixtures("login_limits")
def test_is_login_throttled_when_ip_limit_reached_across_emails() -> None:
    add_failures(1, email="a@example.com", ip="203.0.113.7")
    add_failures(1, email="b@example.com", ip="203.0.113.7")
    add_failures(1, email="c@example.com", ip="203.0.113.7")

    assert is_login_throttled("irfan@example.com", "203.0.113.7")


@pytest.mark.django_db
@pytest.mark.usefixtures("login_limits")
def test_is_login_throttled_when_ipv6_failures_in_same_64() -> None:
    add_failures(2, email="irfan@example.com", ip=mask_ip("2001:db8:1:2::1"))

    assert is_login_throttled("irfan@example.com", "2001:db8:1:2::9")


@pytest.mark.django_db
@pytest.mark.usefixtures("login_limits")
@pytest.mark.parametrize(
    ("seconds_since_last", "throttled"),
    [(29, True), (31, False)],
    ids=["within_backoff", "backoff_elapsed"],
)
def test_is_login_throttled_when_email_limit_reached(
    seconds_since_last: int, throttled: bool
) -> None:
    for host in range(1, 5):
        add_failures(
            1, email="irfan@example.com", ip=f"198.51.100.{host}", seconds_ago=seconds_since_last
        )

    assert is_login_throttled("irfan@example.com", "203.0.113.7") is throttled


@pytest.mark.django_db
@pytest.mark.usefixtures("login_limits")
def test_is_login_throttled_ignores_ip_rules_when_ip_unknown() -> None:
    add_failures(3, email="irfan@example.com", ip=None)

    assert not is_login_throttled("irfan@example.com", None)


@pytest.mark.django_db
@pytest.mark.usefixtures("login_limits")
def test_is_login_throttled_applies_email_rule_when_ip_unknown() -> None:
    add_failures(4, email="irfan@example.com", ip=None)

    assert is_login_throttled("irfan@example.com", None)


@pytest.mark.django_db
@pytest.mark.usefixtures("login_limits")
def test_is_login_throttled_checks_every_rule_in_one_query(
    django_assert_num_queries: DjangoAssertNumQueries,
) -> None:
    with django_assert_num_queries(1):
        is_login_throttled("irfan@example.com", "203.0.113.7")
