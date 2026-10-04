from django.contrib.auth.hashers import make_password
from django.db import IntegrityError, transaction
from psycopg.errors import UniqueViolation

from users.models import User


class UserService:
    def create(self, *, email: str, password: str | None, is_staff: bool = False) -> User:
        return User.objects.create_user(email=email, password=password, is_staff=is_staff)

    # Returns None: callers can't tell new from taken.
    def signup(self, *, email: str, password: str) -> None:
        if User.objects.filter(email=User.objects.normalize_email(email)).exists():
            # Same hashing cost, so timing doesn't tell.
            make_password(password)
            return
        try:
            with transaction.atomic():
                self.create(email=email, password=password)
        except IntegrityError as error:
            if not self._is_lost_email_race(error):
                raise

    # Postgres names unique=True's constraint <table>_<column>_key.
    def _is_lost_email_race(self, error: IntegrityError) -> bool:
        cause = error.__cause__
        return (
            isinstance(cause, UniqueViolation) and cause.diag.constraint_name == "users_email_key"
        )
