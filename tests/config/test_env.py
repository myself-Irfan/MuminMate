import json
import re
from typing import Any

import pytest
from kombu.utils.url import url_to_parts
from pydantic import HttpUrl, ValidationError
from pydantic_settings import SettingsError

from config.env import EmailSettings, Env, LogSettings
from users.limits import EmailLoginLimit, LoginLimit, LoginLimits


@pytest.fixture
def login_limits_data() -> dict[str, Any]:
    return {
        "email_ip": {"max_failures": 5, "window_seconds": 900},
        "ip": {"max_failures": 100, "window_seconds": 900},
        "email": {"max_failures": 20, "window_seconds": 3600, "backoff_seconds": 60},
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
    login_limits_data: dict[str, Any],
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
        "DJANGO_PASSWORD_RESET_TIMEOUT_HOURS": "72",
        "DJANGO_LOGGING": json.dumps(logging_data),
        "DJANGO_LOGIN_LIMITS": json.dumps(login_limits_data),
        "DJANGO_PUBLIC_URL": "https://muminmate.example",
        "DJANGO_EMAIL": json.dumps(email_data),
        "DJANGO_EMAIL_HOST_USER": "",
        "DJANGO_EMAIL_HOST_PASSWORD": "",
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
def test_env_fails_when_hsts_seconds_negative(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DJANGO_HSTS_SECONDS", "-1")

    with pytest.raises(ValidationError, match="django_hsts_seconds"):
        Env(_env_file=None)


@pytest.mark.usefixtures("env_vars")
@pytest.mark.parametrize("var", ["POSTGRES_PORT", "RABBITMQ_PORT"])
@pytest.mark.parametrize("port", ["-1", "65536"])
def test_env_fails_when_port_out_of_range(
    monkeypatch: pytest.MonkeyPatch, var: str, port: str
) -> None:
    monkeypatch.setenv(var, port)

    with pytest.raises(ValidationError, match=var.lower()):
        Env(_env_file=None)


@pytest.mark.usefixtures("env_vars")
def test_rabbitmq_url_round_trips_user_password_and_vhost(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    url_reserved_chars = "p@ss:w/rd"
    for var in ("RABBITMQ_USER", "RABBITMQ_PASSWORD", "RABBITMQ_VHOST"):
        monkeypatch.setenv(var, url_reserved_chars)

    env = Env(_env_file=None)

    parts = url_to_parts(env.rabbitmq_url)
    assert (parts.username, parts.password, parts.path) == (url_reserved_chars,) * 3


@pytest.mark.usefixtures("env_vars")
@pytest.mark.parametrize(
    "var", ["POSTGRES_PASSWORD", "RABBITMQ_USER", "RABBITMQ_PASSWORD", "RABBITMQ_VHOST"]
)
def test_env_fails_when_value_empty(monkeypatch: pytest.MonkeyPatch, var: str) -> None:
    monkeypatch.setenv(var, "")

    with pytest.raises(ValidationError, match=var.lower()):
        Env(_env_file=None)


@pytest.mark.usefixtures("env_vars")
@pytest.mark.parametrize(
    "var",
    [
        "DJANGO_SESSION_IDLE_MINUTES",
        "DJANGO_SESSION_ABSOLUTE_HOURS",
        "DJANGO_PASSWORD_RESET_TIMEOUT_HOURS",
    ],
)
def test_env_fails_when_duration_not_positive(monkeypatch: pytest.MonkeyPatch, var: str) -> None:
    monkeypatch.setenv(var, "0")

    with pytest.raises(ValidationError, match=var.lower()):
        Env(_env_file=None)


# Idle is 180 minutes in env_vars, so 2 hours is shorter.
@pytest.mark.usefixtures("env_vars")
def test_env_fails_when_session_absolute_shorter_than_idle(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DJANGO_SESSION_ABSOLUTE_HOURS", "2")

    with pytest.raises(ValidationError, match="django_session_absolute_hours"):
        Env(_env_file=None)


@pytest.mark.usefixtures("env_vars")
def test_session_absolute_may_equal_idle(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DJANGO_SESSION_ABSOLUTE_HOURS", "3")

    env = Env(_env_file=None)

    assert env.django_session_absolute_hours == 3


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


@pytest.mark.usefixtures("env_vars")
def test_logging_parsed_from_json() -> None:
    env = Env(_env_file=None)

    assert env.django_logging == LogSettings(level="INFO", format="json")


@pytest.mark.parametrize(("key", "value"), [("level", "VERBOSE"), ("format", "xml")])
@pytest.mark.usefixtures("env_vars")
def test_env_fails_when_logging_value_unknown(
    monkeypatch: pytest.MonkeyPatch, logging_data: dict[str, Any], key: str, value: str
) -> None:
    logging_data[key] = value
    monkeypatch.setenv("DJANGO_LOGGING", json.dumps(logging_data))

    with pytest.raises(ValidationError, match=re.escape(f"django_logging.{key}")):
        Env(_env_file=None)


@pytest.mark.usefixtures("env_vars")
def test_env_fails_when_logging_key_unknown(
    monkeypatch: pytest.MonkeyPatch, logging_data: dict[str, Any]
) -> None:
    logging_data["handler"] = "file"
    monkeypatch.setenv("DJANGO_LOGGING", json.dumps(logging_data))

    with pytest.raises(ValidationError, match=re.escape("django_logging.handler")):
        Env(_env_file=None)


@pytest.mark.parametrize("key", ["level", "format"])
@pytest.mark.usefixtures("env_vars")
def test_env_fails_when_logging_key_missing(
    monkeypatch: pytest.MonkeyPatch, logging_data: dict[str, Any], key: str
) -> None:
    del logging_data[key]
    monkeypatch.setenv("DJANGO_LOGGING", json.dumps(logging_data))

    with pytest.raises(ValidationError, match=re.escape(f"django_logging.{key}")):
        Env(_env_file=None)


@pytest.mark.usefixtures("env_vars")
@pytest.mark.parametrize(
    "url", ["https://muminmate.example", "https://muminmate.example/", "http://localhost:8000"]
)
def test_public_url_parsed_when_origin(monkeypatch: pytest.MonkeyPatch, url: str) -> None:
    monkeypatch.setenv("DJANGO_PUBLIC_URL", url)

    env = Env(_env_file=None)

    assert env.django_public_url == HttpUrl(url)


@pytest.mark.usefixtures("env_vars")
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


@pytest.mark.usefixtures("env_vars")
def test_email_parsed_from_json() -> None:
    env = Env(_env_file=None)

    assert env.django_email == EmailSettings(
        host="localhost",
        port=1025,
        use_tls=False,
        timeout_seconds=10,
        default_from_email="MuminMate <no-reply@example.com>",
    )


@pytest.mark.usefixtures("env_vars")
@pytest.mark.parametrize("port", [0, 65536])
def test_env_fails_when_email_port_out_of_range(
    monkeypatch: pytest.MonkeyPatch, email_data: dict[str, Any], port: int
) -> None:
    email_data["port"] = port
    monkeypatch.setenv("DJANGO_EMAIL", json.dumps(email_data))

    with pytest.raises(ValidationError, match=re.escape("django_email.port")):
        Env(_env_file=None)


@pytest.mark.usefixtures("env_vars")
def test_env_fails_when_email_timeout_not_positive(
    monkeypatch: pytest.MonkeyPatch, email_data: dict[str, Any]
) -> None:
    email_data["timeout_seconds"] = 0
    monkeypatch.setenv("DJANGO_EMAIL", json.dumps(email_data))

    with pytest.raises(ValidationError, match=re.escape("django_email.timeout_seconds")):
        Env(_env_file=None)


@pytest.mark.usefixtures("env_vars")
@pytest.mark.parametrize("key", ["host", "default_from_email"])
def test_env_fails_when_email_value_empty(
    monkeypatch: pytest.MonkeyPatch, email_data: dict[str, Any], key: str
) -> None:
    email_data[key] = ""
    monkeypatch.setenv("DJANGO_EMAIL", json.dumps(email_data))

    with pytest.raises(ValidationError, match=re.escape(f"django_email.{key}")):
        Env(_env_file=None)


@pytest.mark.usefixtures("env_vars")
def test_env_fails_when_https_but_public_url_http(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DJANGO_HTTPS", "true")
    monkeypatch.setenv("DJANGO_PUBLIC_URL", "http://muminmate.example")

    with pytest.raises(ValidationError, match="django_public_url"):
        Env(_env_file=None)


@pytest.mark.usefixtures("env_vars")
def test_env_fails_when_email_key_unknown(
    monkeypatch: pytest.MonkeyPatch, email_data: dict[str, Any]
) -> None:
    email_data["use_ssl"] = True
    monkeypatch.setenv("DJANGO_EMAIL", json.dumps(email_data))

    with pytest.raises(ValidationError, match=re.escape("django_email.use_ssl")):
        Env(_env_file=None)


@pytest.mark.usefixtures("env_vars")
def test_env_fails_when_email_key_missing(
    monkeypatch: pytest.MonkeyPatch, email_data: dict[str, Any]
) -> None:
    del email_data["default_from_email"]
    monkeypatch.setenv("DJANGO_EMAIL", json.dumps(email_data))

    with pytest.raises(ValidationError, match=re.escape("django_email.default_from_email")):
        Env(_env_file=None)


@pytest.mark.usefixtures("env_vars")
def test_email_credentials_empty_when_server_needs_no_login() -> None:
    env = Env(_env_file=None)

    assert env.django_email_host_user == ""
    assert env.django_email_host_password.get_secret_value() == ""


@pytest.mark.usefixtures("env_vars")
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
