import structlog
from django.contrib.auth.hashers import make_password
from django.db import IntegrityError, transaction
from psycopg.errors import UniqueViolation

from users.models import User

logger = structlog.get_logger(__name__)


class UserService:
    def create(self, *, email: str, password: str | None, is_staff: bool = False) -> User:
        return User.objects.create_user(email=email, password=password, is_staff=is_staff)

    # Returns None: callers can't tell new from taken.
    def signup(self, *, email: str, password: str) -> None:
        existing_id = self.get_id_by_email(email)
        if existing_id is not None:
            # Same hashing cost, so timing doesn't tell.
            make_password(password)
            logger.info("signup_ignored", reason="email_taken", user_id=existing_id)
            return
        try:
            with transaction.atomic():
                user = self.create(email=email, password=password)
        except IntegrityError as error:
            if not self._is_lost_email_race(error):
                raise
            logger.info("signup_ignored", reason="email_taken", user_id=self.get_id_by_email(email))
        else:
            logger.info("signup_succeeded", user_id=user.pk)

    def get_id_by_email(self, email: str) -> int | None:
        return (
            User.objects.filter(email=User.objects.normalize_email(email))
            .values_list("pk", flat=True)
            .first()
        )

    # Postgres names unique=True's constraint <table>_<column>_key.
    def _is_lost_email_race(self, error: IntegrityError) -> bool:
        cause = error.__cause__
        return (
            isinstance(cause, UniqueViolation) and cause.diag.constraint_name == "users_email_key"
        )
