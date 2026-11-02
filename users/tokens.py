from datetime import timedelta

from django.conf import settings
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.utils import timezone
from django.utils.http import base36_to_int
from django.utils.timesince import timeuntil

from users.models import User


# Django's check_token reads one global timeout; each link here may expire sooner.
class LinkTokenGenerator(PasswordResetTokenGenerator):
    def get_timeout_seconds(self) -> int:
        return settings.PASSWORD_RESET_TIMEOUT

    def check_token(self, user: User | None, token: str | None) -> bool:
        if token is None or not super().check_token(user, token):
            return False
        issued_at = base36_to_int(token.partition("-")[0])
        return self._num_seconds(self._now()) - issued_at <= self.get_timeout_seconds()

    # Same instant on both sides: a later now would read "2 days, 23 hours".
    def describe_lifetime(self) -> str:
        now = timezone.now()
        return timeuntil(now + timedelta(seconds=self.get_timeout_seconds()), now=now)


class EmailVerificationTokenGenerator(LinkTokenGenerator):
    key_salt = "users.tokens.EmailVerificationTokenGenerator"

    # Not Django's password and last_login: logging in mustn't void the link.
    def _make_hash_value(self, user: User, timestamp: int) -> str:
        return f"{user.pk}{user.email}{user.email_verified_at}{timestamp}"


# Own salt; also void the link if the account is deactivated or made staff after sending.
class ConsumerPasswordResetTokenGenerator(LinkTokenGenerator):
    key_salt = "users.tokens.ConsumerPasswordResetTokenGenerator"

    # A reset link can take over the account, so it lives shorter than the others.
    def get_timeout_seconds(self) -> int:
        return settings.PASSWORD_RESET_LINK_TIMEOUT

    def _make_hash_value(self, user: User, timestamp: int) -> str:
        return f"{super()._make_hash_value(user, timestamp)}{user.is_active}{user.is_staff}"


# Own salt, so invite and reset links can't stand in for each other.
class InviteTokenGenerator(LinkTokenGenerator):
    key_salt = "users.tokens.InviteTokenGenerator"

    def _make_hash_value(self, user: User, timestamp: int) -> str:
        return f"{super()._make_hash_value(user, timestamp)}{user.is_active}"
