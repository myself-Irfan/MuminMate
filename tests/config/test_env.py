import json
import re
from typing import Any

import pytest
from pydantic import ValidationError
from pydantic_settings import SettingsError

from config.env import EmailLoginLimit, Env, LoginLimit, LoginLimits


@pytest.fixture
def login_limits_data() -> dict[str, Any]:
    return {
        "email_ip": {"max_failures": 5, "window_seconds": 900},
        "ip": {"max_failures": 100, "window_seconds": 900},
        "email": {"max_failures": 20, "window_seconds": 3600, "backoff_seconds": 60},
    }


@pytest.fixture
def env_vars(monkeypatch: pytest.MonkeyPatch, login_limits_data: dict[str, Any]) -> None:
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
        "DJANGO_HTTPS": "false",
        "DJANGO_HSTS_SECONDS": "0",
        "DJANGO_SESSION_IDLE_SECONDS": "10800",
        "DJANGO_SESSION_ABSOLUTE_SECONDS": "43200",
        "DJANGO_LOGIN_LIMITS": json.dumps(login_limits_data),
    }

    for key, value in values.items():
        monkeypatch.setenv(key, value)


@pytest.mark.usefixtures("env_vars")
def test_allowed_hosts_trimmed_when_padded() -> None:
    env = Env(_env_file=None)

    assert env.django_allowed_hosts == ["example.com", "api.example.com"]


@pytest.mark.usefixtures("env_vars")
def test_env_fails_when_var_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DJANGO_SECRET_KEY")

    with pytest.raises(ValidationError, match="django_secret_key"):
        Env(_env_file=None)


@pytest.mark.usefixtures("env_vars")
def test_env_fails_when_pool_timeout_not_positive(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("POSTGRES_POOL_TIMEOUT_SECONDS", "0")

    with pytest.raises(ValidationError, match="postgres_pool_timeout_seconds"):
        Env(_env_file=None)


@pytest.mark.usefixtures("env_vars")
def test_env_fails_when_session_idle_not_positive(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DJANGO_SESSION_IDLE_SECONDS", "0")

    with pytest.raises(ValidationError, match="django_session_idle_seconds"):
        Env(_env_file=None)


@pytest.mark.usefixtures("env_vars")
def test_env_fails_when_session_absolute_shorter_than_idle(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DJANGO_SESSION_ABSOLUTE_SECONDS", "10799")

    with pytest.raises(ValidationError, match="django_session_absolute_seconds"):
        Env(_env_file=None)


@pytest.mark.usefixtures("env_vars")
def test_login_limits_parsed_from_json() -> None:
    env = Env(_env_file=None)

    assert env.django_login_limits == LoginLimits(
        email_ip=LoginLimit(max_failures=5, window_seconds=900),
        ip=LoginLimit(max_failures=100, window_seconds=900),
        email=EmailLoginLimit(max_failures=20, window_seconds=3600, backoff_seconds=60),
    )


@pytest.mark.parametrize(
    ("rule", "field"),
    [
        ("email_ip", "max_failures"),
        ("email_ip", "window_seconds"),
        ("ip", "max_failures"),
        ("ip", "window_seconds"),
        ("email", "max_failures"),
        ("email", "window_seconds"),
        ("email", "backoff_seconds"),
    ],
)
@pytest.mark.usefixtures("env_vars")
def test_env_fails_when_login_limit_not_positive(
    monkeypatch: pytest.MonkeyPatch, login_limits_data: dict[str, Any], rule: str, field: str
) -> None:
    login_limits_data[rule][field] = 0
    monkeypatch.setenv("DJANGO_LOGIN_LIMITS", json.dumps(login_limits_data))

    with pytest.raises(ValidationError, match=re.escape(f"django_login_limits.{rule}.{field}")):
        Env(_env_file=None)


@pytest.mark.usefixtures("env_vars")
def test_env_fails_when_login_limit_key_unknown(
    monkeypatch: pytest.MonkeyPatch, login_limits_data: dict[str, Any]
) -> None:
    login_limits_data["ip"]["max_failure"] = 100
    monkeypatch.setenv("DJANGO_LOGIN_LIMITS", json.dumps(login_limits_data))

    with pytest.raises(ValidationError, match=re.escape("django_login_limits.ip.max_failure")):
        Env(_env_file=None)


@pytest.mark.usefixtures("env_vars")
def test_env_fails_when_login_limit_key_missing(
    monkeypatch: pytest.MonkeyPatch, login_limits_data: dict[str, Any]
) -> None:
    del login_limits_data["email"]["backoff_seconds"]
    monkeypatch.setenv("DJANGO_LOGIN_LIMITS", json.dumps(login_limits_data))

    with pytest.raises(
        ValidationError, match=re.escape("django_login_limits.email.backoff_seconds")
    ):
        Env(_env_file=None)


@pytest.mark.usefixtures("env_vars")
def test_env_fails_when_login_limits_not_json(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DJANGO_LOGIN_LIMITS", '{"ip": ')

    with pytest.raises(SettingsError, match="django_login_limits"):
        Env(_env_file=None)
