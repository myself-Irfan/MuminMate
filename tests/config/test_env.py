import pytest
from pydantic import ValidationError

from config.env import Env


@pytest.fixture
def env_vars(monkeypatch: pytest.MonkeyPatch) -> None:
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
