import re
from datetime import timedelta

import pytest
from django.utils import timezone
from pytest_django import Settings

from users.models import LoginFailure
from users.selectors import digest_email, is_login_throttled, mask_ip


def add_failures(count: int, *, email: str, ip: str | None, seconds_ago: int = 0) -> None:
    failed_at = timezone.now() - timedelta(seconds=seconds_ago)
    LoginFailure.objects.bulk_create(
        LoginFailure(email_digest=digest_email(email), ip=ip, failed_at=failed_at)
        for _ in range(count)
    )


def test_digest_email_matches_when_email_not_normalized() -> None:
    assert digest_email(" IRFAN@Example.com ") == digest_email("irfan@example.com")


def test_digest_email_differs_when_emails_differ() -> None:
    assert digest_email("ahmed.1995.irfan@gmail.com") != digest_email("ahmed.1997.irfan@gmail.com")


def test_digest_email_is_sha256_hex() -> None:
    digest = digest_email("irfan@example.com")

    assert re.fullmatch(r"[0-9a-f]{64}", digest)


def test_digest_email_changes_when_secret_key_rotated(settings: Settings) -> None:
    before = digest_email("irfan@example.com")

    settings.SECRET_KEY = settings.SECRET_KEY + "-rotated"

    assert digest_email("irfan@example.com") != before


@pytest.mark.parametrize(
    ("address", "masked"),
    [
        ("203.0.113.7", "203.0.113.7"),
        ("2001:db8:1:2:aaaa:bbbb:cccc:dddd", "2001:db8:1:2::"),
        ("::ffff:203.0.113.7", "203.0.113.7"),
    ],
    ids=["ipv4_unchanged", "ipv6_to_64", "ipv4_mapped_ipv6_to_ipv4"],
)
def test_mask_ip(address: str, masked: str) -> None:
    assert mask_ip(address) == masked


def test_mask_ip_matches_within_same_ipv6_64() -> None:
    assert mask_ip("2001:db8:1:2::1") == mask_ip("2001:db8:1:2:ffff:ffff:ffff:ffff")


def test_mask_ip_differs_when_ipv6_64_differs() -> None:
    assert mask_ip("2001:db8:1:2::1") != mask_ip("2001:db8:1:3::1")


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
