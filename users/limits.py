from pydantic import BaseModel, PositiveInt


class LoginLimit(BaseModel, extra="forbid", frozen=True):
    max_failures: PositiveInt
    window_seconds: PositiveInt


class EmailLoginLimit(LoginLimit):
    backoff_seconds: PositiveInt


class LoginLimits(BaseModel, extra="forbid", frozen=True):
    email_ip: LoginLimit
    ip: LoginLimit
    email: EmailLoginLimit
