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
    }

    for key, value in values.items():
        monkeypatch.setenv(key, value)


@pytest.mark.usefixtures("env_vars")
def test_allowed_hosts_split_trimmed() -> None:
    env = Env(_env_file=None)

    assert env.django_allowed_hosts == ["example.com", "api.example.com"]


@pytest.mark.usefixtures("env_vars")
def test_missing_var_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DJANGO_SECRET_KEY")

    with pytest.raises(ValidationError, match="django_secret_key"):
        Env(_env_file=None)
