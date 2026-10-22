from datetime import timedelta
from pathlib import Path
from typing import Annotated, Literal, Self
from urllib.parse import quote

from pydantic import (
    BaseModel,
    Field,
    HttpUrl,
    NonNegativeInt,
    PositiveInt,
    SecretStr,
    field_validator,
    model_validator,
)
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

from users.limits import ThrottleLimits


class LogSettings(BaseModel, extra="forbid", frozen=True):
    level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
    format: Literal["json", "console"]


class EmailSettings(BaseModel, extra="forbid", frozen=True):
    host: Annotated[str, Field(min_length=1)]
    port: Annotated[int, Field(ge=1, le=65535)]
    use_tls: bool
    timeout_seconds: PositiveInt
    default_from_email: Annotated[str, Field(min_length=1)]


class Env(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parent.parent / ".env", extra="ignore"
    )

    django_secret_key: SecretStr
    django_debug: bool
    django_allowed_hosts: Annotated[list[str], NoDecode]
    django_public_url: HttpUrl
    django_https: bool
    django_hsts_seconds: NonNegativeInt
    django_session_idle_minutes: PositiveInt
    django_session_absolute_hours: PositiveInt
    django_password_reset_timeout_hours: PositiveInt
    django_logging: LogSettings
    django_throttle_limits: ThrottleLimits
    django_email: EmailSettings
    django_email_host_user: str
    django_email_host_password: SecretStr

    postgres_db: str
    postgres_user: str
    postgres_password: Annotated[SecretStr, Field(min_length=1)]
    postgres_host: str
    # 0 only as the Dockerfile's build-time placeholder.
    postgres_port: Annotated[int, Field(ge=0, le=65535)]
    postgres_pool_timeout_seconds: PositiveInt

    rabbitmq_host: str
    # 0 only as the Dockerfile's build-time placeholder.
    rabbitmq_port: Annotated[int, Field(ge=0, le=65535)]
    rabbitmq_user: Annotated[str, Field(min_length=1)]
    rabbitmq_password: Annotated[SecretStr, Field(min_length=1)]
    rabbitmq_vhost: Annotated[str, Field(min_length=1)]

    @property
    def rabbitmq_url(self) -> str:
        user = quote(self.rabbitmq_user, safe="")
        password = quote(self.rabbitmq_password.get_secret_value(), safe="")
        vhost = quote(self.rabbitmq_vhost, safe="")
        return f"amqp://{user}:{password}@{self.rabbitmq_host}:{self.rabbitmq_port}/{vhost}"

    @field_validator("django_allowed_hosts", mode="before")
    @classmethod
    def parse_allowed_hosts(cls, value: str) -> list[str]:
        return [host.strip() for host in value.split(",") if host.strip()]

    @field_validator("django_public_url")
    @classmethod
    def check_public_url_is_origin(cls, url: HttpUrl) -> HttpUrl:
        if url.path != "/" or url.query or url.fragment or url.username or url.password:
            raise ValueError("must be scheme://host[:port] only")
        return url

    @model_validator(mode="after")
    def check_session_absolute_covers_idle(self) -> Self:
        absolute = timedelta(hours=self.django_session_absolute_hours)
        if absolute < timedelta(minutes=self.django_session_idle_minutes):
            raise ValueError(
                "django_session_absolute_hours must be at least django_session_idle_minutes"
            )
        return self

    # Mail links must not downgrade a site served over HTTPS.
    @model_validator(mode="after")
    def check_public_url_https_when_served_over_https(self) -> Self:
        if self.django_https and self.django_public_url.scheme != "https":
            raise ValueError("django_public_url must use https when django_https is true")
        return self

    @model_validator(mode="after")
    def check_email_credentials_set_together(self) -> Self:
        if bool(self.django_email_host_user) != bool(self.django_email_host_password):
            raise ValueError(
                "django_email_host_user and django_email_host_password must be set together"
            )
        return self
