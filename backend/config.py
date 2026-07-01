from datetime import timedelta

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # database
    db_user: str = Field()
    db_password: str = Field()
    db_host: str = Field()
    db_port: int = Field()
    db_name: str = Field()
    test_database_url: str = Field(default="")

    @property
    def db_url(self) -> str:
        return f"postgresql+asyncpg://{self.db_user}:{self.db_password}@{self.db_host}:{self.db_port}/{self.db_name}"

    # security
    secret_key: str = Field()
    algorithm: str = Field(default="HS256")

    # logging
    log_level: str = Field(default="INFO")
    masking_keys: str = Field(default="password,authorization,token,secret,cookie")

    @property
    def masking_keys_set(self) -> set[str]:
        return {k.strip().lower() for k in self.masking_keys.split(",") if k.strip()}

    # ollama
    ollama_base_url: str = Field(default="http://localhost:11434")
    ollama_chat_model: str = Field(default="llama3.1:7b")
    ollama_embed_model: str = Field(default="nomic-embed-text")

    # auth tokens
    access_token_expire_minutes: int = Field(default=15)
    refresh_token_expire_days: int = Field(default=7)

    @property
    def access_token_expire(self) -> timedelta:
        return timedelta(minutes=self.access_token_expire_minutes)

    @property
    def refresh_token_expire(self) -> timedelta:
        return timedelta(days=self.refresh_token_expire_days)

    # cleanup
    cleanup_interval_hours: int = Field(default=24)
    thread_expiry_days: int = Field(default=30)

    @property
    def cleanup_interval(self) -> timedelta:
        return timedelta(hours=self.cleanup_interval_hours)

    @property
    def thread_expiry(self) -> timedelta:
        return timedelta(days=self.thread_expiry_days)

    # cache
    cache_similarity_threshold: float = Field(default=0.92)
    cache_expiry_days: int = Field(default=90)

    @property
    def cache_expiry(self) -> timedelta:
        return timedelta(days=self.cache_expiry_days)

    # lockout
    login_attempt_window_minutes: int = Field(default=15)
    login_attempt_max_failures: int = Field(default=5)
    login_attempt_retain_hours: int = Field(default=24)

    @property
    def login_attempt_window(self) -> timedelta:
        return timedelta(minutes=self.login_attempt_window_minutes)

    @property
    def login_attempt_retain(self) -> timedelta:
        return timedelta(hours=self.login_attempt_retain_hours)

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


settings = Settings()
