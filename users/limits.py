from typing import Self

from pydantic import BaseModel, ConfigDict, PositiveInt, model_validator


# One class per scope in DJANGO_THROTTLE_LIMITS, its rules as flat fields.
class LoginLimits(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    email_ip_max_events: PositiveInt
    email_ip_window_seconds: PositiveInt
    ip_max_events: PositiveInt
    ip_window_seconds: PositiveInt
    email_max_events: PositiveInt
    email_window_seconds: PositiveInt
    email_backoff_seconds: PositiveInt


class PasswordResetLimits(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    email_max_events: PositiveInt
    email_window_seconds: PositiveInt
    email_cooldown_seconds: PositiveInt
    ip_max_events: PositiveInt
    ip_window_seconds: PositiveInt

    # A cooldown as long as the window would make the cap meaningless.
    @model_validator(mode="after")
    def _validate_cooldown_within_window(self) -> Self:
        if self.email_cooldown_seconds >= self.email_window_seconds:
            raise ValueError("email_cooldown_seconds must be shorter than email_window_seconds")
        return self


class SignupLimits(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    ip_max_events: PositiveInt
    ip_window_seconds: PositiveInt


# Per email only: only a password holder can trigger a resend.
class VerificationEmailLimits(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    email_max_events: PositiveInt
    email_window_seconds: PositiveInt
    email_cooldown_seconds: PositiveInt

    @model_validator(mode="after")
    def _validate_cooldown_within_window(self) -> Self:
        if self.email_cooldown_seconds >= self.email_window_seconds:
            raise ValueError("email_cooldown_seconds must be shorter than email_window_seconds")
        return self


class ThrottleLimits(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    login: LoginLimits
    password_reset: PasswordResetLimits
    signup: SignupLimits
    verification_email: VerificationEmailLimits
