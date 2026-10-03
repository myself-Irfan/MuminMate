import re

import pytest
from pytest_django import Settings

from users.throttling import digest_email, mask_ip


def test_digest_email_matches_when_email_not_normalized() -> None:
    assert digest_email(" IRFAN@Example.com ") == digest_email("irfan@example.com")


def test_digest_email_differs_when_emails_differ() -> None:
    assert digest_email("user.1995@example.com") != digest_email("user.1997@example.com")


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
