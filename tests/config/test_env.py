import json
import re
from typing import Any

import pytest
from kombu.utils.url import url_to_parts
from pydantic import HttpUrl, ValidationError
from pydantic_settings import SettingsError

from config.env import EmailSettings, Env, LogSettings
from users.limits import (
    LoginLimits,
    PasswordResetLimits,
    SignupLimits,
    ThrottleLimits,
    VerificationEmailLimits,
)

pytestmark = pytest.mark.usefixtures("env_vars")


@pytest.fixture
def throttle_limits_data() -> dict[str, Any]:
    return {
        "login": {
            "email_ip_max_events": 5,
            "email_ip_window_seconds": 900,
            "ip_max_events": 100,
            "ip_window_seconds": 900,
            "email_max_events": 20,
            "email_window_seconds": 3600,
            "email_backoff_seconds": 60,
        },
        "password_reset": {
            "email_max_events": 3,
            "email_window_seconds": 3600,
            "email_cooldown_seconds": 300,
            "ip_max_events": 100,
            "ip_window_seconds": 3600,
        },
        "signup": {"ip_max_events": 50, "ip_window_seconds": 3600},
        "verification_email": {
            "email_max_events": 3,
            "email_window_seconds": 3600,
            "email_cooldown_seconds": 300,
        },
    }


@pytest.fixture
def logging_data() -> dict[str, Any]:
    return {"level": "INFO", "format": "json"}


@pytest.fixture
def email_data() -> dict[str, Any]:
    return {
        "host": "localhost",
        "port": 1025,
        "use_tls": False,
        "timeout_seconds": 10,
        "default_from_email": "MuminMate <no-reply@example.com>",
    }


@pytest.fixture
def env_vars(
    monkeypatch: pytest.MonkeyPatch,
    logging_data: dict[str, Any],
    throttle_limits_data: dict[str, Any],
    email_data: dict[str, Any],
) -> None:
    values = {
        "DJANGO_SECRET_KEY": "test-secret",
        "DJANGO_DEBUG": "false",
        "DJANGO_ALLOWED_HOSTS": " example.com, ,api.example.com,",
        "POSTGRES_DB": "db",
        "POSTGRES_USER": "user",
        "POSTGRES_PASSWORD": "password",
        "POSTGRES_HOST": "localhost",
        "POSTGRES_PORT": "5432",
        "POSTGRES_POOL_TIMEOUT_SECONDS": "5",
        "RABBITMQ_HOST": "localhost",
        "RABBITMQ_PORT": "5672",
        "RABBITMQ_USER": "user",
        "RABBITMQ_PASSWORD": "password",
        "RABBITMQ_VHOST": "muminmate",
        "DJANGO_HTTPS": "false",
        "DJANGO_HSTS_SECONDS": "0",
        "DJANGO_SESSION_IDLE_MINUTES": "180",
        "DJANGO_SESSION_ABSOLUTE_HOURS": "12",
        "DJANGO_EMAIL_LINK_TIMEOUT_HOURS": "72",
        "DJANGO_LOGGING": json.dumps(logging_data),
        "DJANGO_THROTTLE_LIMITS": json.dumps(throttle_limits_data),
        "DJANGO_PUBLIC_URL": "https://muminmate.example",
        "DJANGO_EMAIL": json.dumps(email_data),
        "DJANGO_EMAIL_HOST_USER": "",
        "DJANGO_EMAIL_HOST_PASSWORD": "",
        "FORWARDED_ALLOW_IPS": "10.0.0.1, 10.42.0.0/16, ::1",
    }

    for key, value in values.items():
        monkeypatch.setenv(key, value)


def test_allowed_hosts_trimmed_when_padded() -> None:
    env = Env(_env_file=None)

    assert env.django_allowed_hosts == ["example.com", "api.example.com"]


def test_forwarded_allow_ips_accepts_addresses_and_networks() -> None:
    assert Env(_env_file=None).forwarded_allow_ips == "10.0.0.1, 10.42.0.0/16, ::1"


# uvicorn's default would trust only localhost, so every client shares the proxy's IP.
def test_env_fails_when_forwarded_allow_ips_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("FORWARDED_ALLOW_IPS")

    with pytest.raises(ValidationError, match="forwarded_allow_ips"):
        Env(_env_file=None)


def test_env_fails_when_var_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DJANGO_SECRET_KEY")

    with pytest.raises(ValidationError, match="django_secret_key"):
        Env(_env_file=None)


@pytest.mark.parametrize(
    ("var", "value"),
    [
        ("POSTGRES_POOL_TIMEOUT_SECONDS", "0"),
        ("DJANGO_HSTS_SECONDS", "-1"),
        ("POSTGRES_PORT", "-1"),
        ("POSTGRES_PORT", "65536"),
        ("RABBITMQ_PORT", "-1"),
        ("RABBITMQ_PORT", "65536"),
        ("POSTGRES_DB", ""),
        ("POSTGRES_USER", ""),
        ("POSTGRES_PASSWORD", ""),
        ("POSTGRES_HOST", ""),
        ("RABBITMQ_HOST", ""),
        ("RABBITMQ_USER", ""),
        ("RABBITMQ_PASSWORD", ""),
        ("RABBITMQ_VHOST", ""),
        ("DJANGO_SESSION_IDLE_MINUTES", "0"),
        ("DJANGO_SESSION_ABSOLUTE_HOURS", "0"),
        ("DJANGO_EMAIL_LINK_TIMEOUT_HOURS", "0"),
        # Idle is 180 minutes in env_vars, so 2 hours is shorter.
        ("DJANGO_SESSION_ABSOLUTE_HOURS", "2"),
        ("FORWARDED_ALLOW_IPS", ""),
        ("FORWARDED_ALLOW_IPS", "*"),
        ("FORWARDED_ALLOW_IPS", "10.0.0.1, *"),
        # uvicorn would keep these as literals that never match: trust silently off.
        ("FORWARDED_ALLOW_IPS", "10.0.0.1/8"),
        ("FORWARDED_ALLOW_IPS", "proxy.local"),
    ],
    ids=[
        "pool_timeout_zero",
        "hsts_negative",
        "postgres_port_negative",
        "postgres_port_too_big",
        "rabbitmq_port_negative",
        "rabbitmq_port_too_big",
        "postgres_db_empty",
        "postgres_user_empty",
        "postgres_password_empty",
        "postgres_host_empty",
        "rabbitmq_host_empty",
        "rabbitmq_user_empty",
        "rabbitmq_password_empty",
        "rabbitmq_vhost_empty",
        "session_idle_zero",
        "session_absolute_zero",
        "email_link_timeout_zero",
        "session_absolute_shorter_than_idle",
        "forwarded_allow_ips_empty",
        "forwarded_allow_ips_any",
        "forwarded_allow_ips_any_in_list",
        "forwarded_allow_ips_host_bits_set",
        "forwarded_allow_ips_hostname",
    ],
)
def test_env_fails_when_value_invalid(
    monkeypatch: pytest.MonkeyPatch, var: str, value: str
) -> None:
    monkeypatch.setenv(var, value)

    with pytest.raises(ValidationError, match=var.lower()):
        Env(_env_file=None)


def test_rabbitmq_url_round_trips_user_password_and_vhost(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    url_reserved_chars = "p@ss:w/rd"
    for var in ("RABBITMQ_USER", "RABBITMQ_PASSWORD", "RABBITMQ_VHOST"):
        monkeypatch.setenv(var, url_reserved_chars)

    env = Env(_env_file=None)

    parts = url_to_parts(env.rabbitmq_url)
    assert (parts.username, parts.password, parts.path) == (url_reserved_chars,) * 3


def test_session_absolute_may_equal_idle(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DJANGO_SESSION_ABSOLUTE_HOURS", "3")

    env = Env(_env_file=None)

    assert env.django_session_absolute_hours == 3


def test_throttle_limits_parsed_from_json() -> None:
    env = Env(_env_file=None)

    assert env.django_throttle_limits == ThrottleLimits(
        login=LoginLimits(
            email_ip_max_events=5,
            email_ip_window_seconds=900,
            ip_max_events=100,
            ip_window_seconds=900,
            email_max_events=20,
            email_window_seconds=3600,
            email_backoff_seconds=60,
        ),
        password_reset=PasswordResetLimits(
            email_max_events=3,
            email_window_seconds=3600,
            email_cooldown_seconds=300,
            ip_max_events=100,
            ip_window_seconds=3600,
        ),
        signup=SignupLimits(ip_max_events=50, ip_window_seconds=3600),
        verification_email=VerificationEmailLimits(
            email_max_events=3, email_window_seconds=3600, email_cooldown_seconds=300
        ),
    )


@pytest.mark.parametrize(
    ("scope", "field"),
    [
        ("login", "email_ip_max_events"),
        ("login", "email_ip_window_seconds"),
        ("login", "ip_max_events"),
        ("login", "ip_window_seconds"),
        ("login", "email_max_events"),
        ("login", "email_window_seconds"),
        ("login", "email_backoff_seconds"),
        ("password_reset", "email_max_events"),
        ("password_reset", "email_window_seconds"),
        ("password_reset", "email_cooldown_seconds"),
        ("password_reset", "ip_max_events"),
        ("password_reset", "ip_window_seconds"),
        ("signup", "ip_max_events"),
        ("signup", "ip_window_seconds"),
        ("verification_email", "email_max_events"),
        ("verification_email", "email_window_seconds"),
        ("verification_email", "email_cooldown_seconds"),
    ],
)
def test_env_fails_when_throttle_limit_not_positive(
    monkeypatch: pytest.MonkeyPatch, throttle_limits_data: dict[str, Any], scope: str, field: str
) -> None:
    throttle_limits_data[scope][field] = 0
    monkeypatch.setenv("DJANGO_THROTTLE_LIMITS", json.dumps(throttle_limits_data))

    with pytest.raises(ValidationError, match=re.escape(f"django_throttle_limits.{scope}.{field}")):
        Env(_env_file=None)


@pytest.mark.parametrize("scope", ["password_reset", "verification_email"])
@pytest.mark.parametrize("cooldown_seconds", [3600, 3601])
def test_env_fails_when_cooldown_not_shorter_than_window(
    monkeypatch: pytest.MonkeyPatch,
    throttle_limits_data: dict[str, Any],
    scope: str,
    cooldown_seconds: int,
) -> None:
    throttle_limits_data[scope]["email_cooldown_seconds"] = cooldown_seconds
    monkeypatch.setenv("DJANGO_THROTTLE_LIMITS", json.dumps(throttle_limits_data))

    with pytest.raises(ValidationError, match="email_cooldown_seconds must be shorter"):
        Env(_env_file=None)


def test_env_fails_when_throttle_limit_field_unknown(
    monkeypatch: pytest.MonkeyPatch, throttle_limits_data: dict[str, Any]
) -> None:
    throttle_limits_data["signup"]["email_max_events"] = 3
    monkeypatch.setenv("DJANGO_THROTTLE_LIMITS", json.dumps(throttle_limits_data))

    with pytest.raises(
        ValidationError, match=re.escape("django_throttle_limits.signup.email_max_events")
    ):
        Env(_env_file=None)


def test_env_fails_when_throttle_limit_field_missing(
    monkeypatch: pytest.MonkeyPatch, throttle_limits_data: dict[str, Any]
) -> None:
    del throttle_limits_data["login"]["email_backoff_seconds"]
    monkeypatch.setenv("DJANGO_THROTTLE_LIMITS", json.dumps(throttle_limits_data))

    with pytest.raises(
        ValidationError, match=re.escape("django_throttle_limits.login.email_backoff_seconds")
    ):
        Env(_env_file=None)


def test_env_fails_when_throttle_limit_scope_missing(
    monkeypatch: pytest.MonkeyPatch, throttle_limits_data: dict[str, Any]
) -> None:
    del throttle_limits_data["signup"]
    monkeypatch.setenv("DJANGO_THROTTLE_LIMITS", json.dumps(throttle_limits_data))

    with pytest.raises(ValidationError, match=re.escape("django_throttle_limits.signup")):
        Env(_env_file=None)


def test_env_fails_when_throttle_limits_not_json(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DJANGO_THROTTLE_LIMITS", '{"login": ')

    with pytest.raises(SettingsError, match="django_throttle_limits"):
        Env(_env_file=None)


def test_logging_parsed_from_json() -> None:
    env = Env(_env_file=None)

    assert env.django_logging == LogSettings(level="INFO", format="json")


@pytest.mark.parametrize(("key", "value"), [("level", "VERBOSE"), ("format", "xml")])
def test_env_fails_when_logging_value_unknown(
    monkeypatch: pytest.MonkeyPatch, logging_data: dict[str, Any], key: str, value: str
) -> None:
    logging_data[key] = value
    monkeypatch.setenv("DJANGO_LOGGING", json.dumps(logging_data))

    with pytest.raises(ValidationError, match=re.escape(f"django_logging.{key}")):
        Env(_env_file=None)


def test_env_fails_when_logging_key_unknown(
    monkeypatch: pytest.MonkeyPatch, logging_data: dict[str, Any]
) -> None:
    logging_data["handler"] = "file"
    monkeypatch.setenv("DJANGO_LOGGING", json.dumps(logging_data))

    with pytest.raises(ValidationError, match=re.escape("django_logging.handler")):
        Env(_env_file=None)


@pytest.mark.parametrize("key", ["level", "format"])
def test_env_fails_when_logging_key_missing(
    monkeypatch: pytest.MonkeyPatch, logging_data: dict[str, Any], key: str
) -> None:
    del logging_data[key]
    monkeypatch.setenv("DJANGO_LOGGING", json.dumps(logging_data))

    with pytest.raises(ValidationError, match=re.escape(f"django_logging.{key}")):
        Env(_env_file=None)


@pytest.mark.parametrize(
    "url", ["https://muminmate.example", "https://muminmate.example/", "http://localhost:8000"]
)
def test_public_url_parsed_when_origin(monkeypatch: pytest.MonkeyPatch, url: str) -> None:
    monkeypatch.setenv("DJANGO_PUBLIC_URL", url)

    env = Env(_env_file=None)

    assert env.django_public_url == HttpUrl(url)


@pytest.mark.parametrize(
    "url",
    [
        "muminmate.example",
        "ftp://muminmate.example",
        "https://muminmate.example/app",
        "https://muminmate.example?next=home",
        "https://muminmate.example#top",
        "https://user@muminmate.example",
        "https://:secret@muminmate.example",
    ],
)
def test_env_fails_when_public_url_not_origin(monkeypatch: pytest.MonkeyPatch, url: str) -> None:
    monkeypatch.setenv("DJANGO_PUBLIC_URL", url)

    with pytest.raises(ValidationError, match="django_public_url"):
        Env(_env_file=None)


def test_email_parsed_from_json() -> None:
    env = Env(_env_file=None)

    assert env.django_email == EmailSettings(
        host="localhost",
        port=1025,
        use_tls=False,
        timeout_seconds=10,
        default_from_email="MuminMate <no-reply@example.com>",
    )


@pytest.mark.parametrize("port", [0, 65536])
def test_env_fails_when_email_port_out_of_range(
    monkeypatch: pytest.MonkeyPatch, email_data: dict[str, Any], port: int
) -> None:
    email_data["port"] = port
    monkeypatch.setenv("DJANGO_EMAIL", json.dumps(email_data))

    with pytest.raises(ValidationError, match=re.escape("django_email.port")):
        Env(_env_file=None)


def test_env_fails_when_email_timeout_not_positive(
    monkeypatch: pytest.MonkeyPatch, email_data: dict[str, Any]
) -> None:
    email_data["timeout_seconds"] = 0
    monkeypatch.setenv("DJANGO_EMAIL", json.dumps(email_data))

    with pytest.raises(ValidationError, match=re.escape("django_email.timeout_seconds")):
        Env(_env_file=None)


@pytest.mark.parametrize("key", ["host", "default_from_email"])
def test_env_fails_when_email_value_empty(
    monkeypatch: pytest.MonkeyPatch, email_data: dict[str, Any], key: str
) -> None:
    email_data[key] = ""
    monkeypatch.setenv("DJANGO_EMAIL", json.dumps(email_data))

    with pytest.raises(ValidationError, match=re.escape(f"django_email.{key}")):
        Env(_env_file=None)


def test_env_fails_when_https_but_public_url_http(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DJANGO_HTTPS", "true")
    monkeypatch.setenv("DJANGO_PUBLIC_URL", "http://muminmate.example")

    with pytest.raises(ValidationError, match="django_public_url"):
        Env(_env_file=None)


def test_env_fails_when_email_key_unknown(
    monkeypatch: pytest.MonkeyPatch, email_data: dict[str, Any]
) -> None:
    email_data["use_ssl"] = True
    monkeypatch.setenv("DJANGO_EMAIL", json.dumps(email_data))

    with pytest.raises(ValidationError, match=re.escape("django_email.use_ssl")):
        Env(_env_file=None)


def test_env_fails_when_email_key_missing(
    monkeypatch: pytest.MonkeyPatch, email_data: dict[str, Any]
) -> None:
    del email_data["default_from_email"]
    monkeypatch.setenv("DJANGO_EMAIL", json.dumps(email_data))

    with pytest.raises(ValidationError, match=re.escape("django_email.default_from_email")):
        Env(_env_file=None)


def test_email_credentials_empty_when_server_needs_no_login() -> None:
    env = Env(_env_file=None)

    assert env.django_email_host_user == ""
    assert env.django_email_host_password.get_secret_value() == ""


@pytest.mark.parametrize(
    ("var", "value"),
    [("DJANGO_EMAIL_HOST_USER", "sender"), ("DJANGO_EMAIL_HOST_PASSWORD", "secret")],
)
def test_env_fails_when_email_credentials_half_set(
    monkeypatch: pytest.MonkeyPatch, var: str, value: str
) -> None:
    monkeypatch.setenv(var, value)

    with pytest.raises(ValidationError, match="django_email_host_user"):
        Env(_env_file=None)
