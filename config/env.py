from typing import Annotated
from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

class Env(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    django_secret_key: SecretStr
    django_debug: bool
    django_allowed_hosts: Annotated[list[str], NoDecode]

    @field_validator("django_allowed_hosts", mode="before")
    @classmethod
    def split_commas(cls, value: str) -> list[str]:
        return [host.strip() for host in value.split(",") if host.strip()]

    postgres_db: str
    postgres_user: str
    postgres_password: SecretStr
    postgres_host: str
    postgres_port: int