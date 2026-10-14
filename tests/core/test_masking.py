import pytest

from core.masking import DataMasker


@pytest.fixture
def masker() -> DataMasker:
    return DataMasker()


def test_mask_redacts_sensitive_values_at_any_depth(masker: DataMasker) -> None:
    data = {
        "api_key": ["sk-1", "sk-2"],
        "metric": ["top"],
        "nested": {"Password": 1234, "items": ({"X-Api-Key": "k"}, {"ok": "v"})},
    }

    assert masker.mask(data) == {
        "api_key": [masker.replacement] * 2,
        "metric": ["top"],
        "nested": {
            "Password": masker.replacement,
            "items": [{"X-Api-Key": masker.replacement}, {"ok": "v"}],
        },
    }


@pytest.mark.parametrize(
    "key",
    [
        "api_key",
        "API-KEY",
        "apiKey",
        "x-api-key",
        "XAPIKey",
        "token",
        "Password",
        "access_token",
        "accessToken",
        "X-Auth-Token",
        "client_secret",
        "session_id",
        "X-CSRFToken",
        "jwt",
        "key",
        "KEY",
        "Set-Cookie",
        "set_cookie",
        "db_password",
        "new_password",
        "password_confirmation",
        "user[password]",
        "user.password",
        "github_token",
        "otp_code",
        "aws_access_key_id",
        "encryption_key",
        "signing_key",
        "pwd",
        "pincode",
        "gcp_credentials",
    ],
)
def test_is_sensitive_when_key_names_a_secret(masker: DataMasker, key: str) -> None:
    assert masker.is_sensitive(key)


@pytest.mark.parametrize(
    "key",
    ["metric", "author", "prompt_tokens", "sort_key", "session_count", "auth_method", "pin_count"],
)
def test_is_sensitive_false_when_key_is_ordinary(masker: DataMasker, key: str) -> None:
    assert not masker.is_sensitive(key)


def test_mask_keeps_non_string_keys(masker: DataMasker) -> None:
    assert masker.mask({1: "one", None: "none"}) == {1: "one", None: "none"}


def test_mask_query_changes_only_sensitive_values(masker: DataMasker) -> None:
    masked = masker.mask_query("q=b%20c+d&api_key=s&TOKEN=t&empty=&flag")

    assert masked == (
        f"q=b%20c+d&api_key={masker.replacement}&TOKEN={masker.replacement}&empty=&flag"
    )


def test_mask_query_decodes_keys_before_matching(masker: DataMasker) -> None:
    assert masker.mask_query("api%5Fkey=s") == f"api%5Fkey={masker.replacement}"
