from pathlib import Path
from typing import Annotated, Self

from pydantic import PositiveInt, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Env(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parent.parent / ".env", extra="ignore"
    )

    django_secret_key: SecretStr
    django_debug: bool
    django_allowed_hosts: Annotated[list[str], NoDecode]
    django_https: bool
    django_hsts_seconds: int
    django_session_idle_seconds: PositiveInt
    django_session_absolute_seconds: PositiveInt

    postgres_db: str
    postgres_user: str
    postgres_password: SecretStr
    postgres_host: str
    postgres_port: int
    postgres_pool_timeout_seconds: PositiveInt

    @field_validator("django_allowed_hosts", mode="before")
    @classmethod
    def parse_allowed_hosts(cls, value: str) -> list[str]:
        return [host.strip() for host in value.split(",") if host.strip()]

    @model_validator(mode="after")
    def check_session_absolute_covers_idle(self) -> Self:
        if self.django_session_absolute_seconds < self.django_session_idle_seconds:
            raise ValueError(
                "django_session_absolute_seconds must be at least django_session_idle_seconds"
            )
        return self
