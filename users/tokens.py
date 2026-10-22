from datetime import timedelta

from django.conf import settings
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.utils import timezone
from django.utils.timesince import timeuntil

from users.models import User


class EmailVerificationTokenGenerator(PasswordResetTokenGenerator):
    key_salt = "users.tokens.EmailVerificationTokenGenerator"

    # Not Django's password and last_login: logging in mustn't void the link.
    def _make_hash_value(self, user: User, timestamp: int) -> str:
        return f"{user.pk}{user.email}{user.email_verified_at}{timestamp}"


# Own salt; also void the link if the account is deactivated or made staff after sending.
class ConsumerPasswordResetTokenGenerator(PasswordResetTokenGenerator):
    key_salt = "users.tokens.ConsumerPasswordResetTokenGenerator"

    def _make_hash_value(self, user: User, timestamp: int) -> str:
        return f"{super()._make_hash_value(user, timestamp)}{user.is_active}{user.is_staff}"


# Own salt, so invite and reset links can't stand in for each other.
class InviteTokenGenerator(PasswordResetTokenGenerator):
    key_salt = "users.tokens.InviteTokenGenerator"

    def _make_hash_value(self, user: User, timestamp: int) -> str:
        return f"{super()._make_hash_value(user, timestamp)}{user.is_active}"


# Same instant on both sides: a later now would read "2 days, 23 hours".
def describe_token_lifetime() -> str:
    now = timezone.now()
    return timeuntil(now + timedelta(seconds=settings.PASSWORD_RESET_TIMEOUT), now=now)
