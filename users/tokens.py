from django.contrib.auth.tokens import PasswordResetTokenGenerator

from users.models import User


class EmailVerificationTokenGenerator(PasswordResetTokenGenerator):
    key_salt = "users.tokens.EmailVerificationTokenGenerator"

    # Not Django's password and last_login: logging in mustn't void the link.
    def _make_hash_value(self, user: User, timestamp: int) -> str:
        return f"{user.pk}{user.email}{user.email_verified_at}{timestamp}"
