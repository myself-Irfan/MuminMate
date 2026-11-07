from dataclasses import dataclass
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.core import signing
from django.utils import timezone
from django.utils.crypto import constant_time_compare, salted_hmac
from django.utils.http import base36_to_int
from django.utils.timesince import timeuntil

from users.models import User


# Same instant on both sides: a later now would read "2 days, 23 hours".
def describe_lifetime(seconds: int) -> str:
    now = timezone.now()
    return timeuntil(now + timedelta(seconds=seconds), now=now)


# Django's check_token reads one global timeout; each link here may expire sooner.
class LinkTokenGenerator(PasswordResetTokenGenerator):
    def get_timeout_seconds(self) -> int:
        return settings.PASSWORD_RESET_TIMEOUT

    def check_token(self, user: User | None, token: str | None) -> bool:
        if token is None or not super().check_token(user, token):
            return False
        issued_at = base36_to_int(token.partition("-")[0])
        return self._num_seconds(self._now()) - issued_at <= self.get_timeout_seconds()

    def describe_lifetime(self) -> str:
        return describe_lifetime(self.get_timeout_seconds())


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


@dataclass(frozen=True)
class EmailChangeClaim:
    user_id: int
    new_email: str
    fingerprint: str


# No pending email is stored: the new address travels in the signed link.
class EmailChangeSigner:
    salt = "users.tokens.EmailChangeSigner"

    def make_token(self, user: User, new_email: str) -> str:
        return signing.dumps(
            {"user_id": user.pk, "new_email": new_email, "fingerprint": self._fingerprint(user)},
            salt=self.salt,
        )

    def describe_lifetime(self) -> str:
        return describe_lifetime(settings.EMAIL_CHANGE_LINK_TIMEOUT)

    # SignatureExpired is a BadSignature.
    def read_token(self, token: str) -> EmailChangeClaim | None:
        try:
            value = signing.loads(token, salt=self.salt, max_age=settings.EMAIL_CHANGE_LINK_TIMEOUT)
        except signing.BadSignature:
            return None
        return EmailChangeClaim(**value)

    # A password, email or confirmation change since sending voids the link.
    def is_current(self, user: User, claim: EmailChangeClaim) -> bool:
        return constant_time_compare(self._fingerprint(user), claim.fingerprint)

    def _fingerprint(self, user: User) -> str:
        return salted_hmac(
            self.salt, f"{user.pk}{user.email}{user.password}{user.email_verified_at}"
        ).hexdigest()
