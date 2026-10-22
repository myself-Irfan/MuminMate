import structlog
from django.db import IntegrityError, transaction
from psycopg.errors import UniqueViolation

from users.exceptions import EmailTakenError
from users.models import User
from users.services.email_verification_service import EmailVerificationService

logger = structlog.get_logger(__name__)


class UserService:
    def create(self, *, email: str, password: str | None, is_staff: bool = False) -> User:
        return User.objects.create_user(email=email, password=password, is_staff=is_staff)

    def signup(self, *, email: str, password: str) -> None:
        user = self._create_signup_user(email, password)
        EmailVerificationService().request_verification(user)

    def get_id_by_email(self, email: str) -> int | None:
        try:
            return User.objects.values_list("pk", flat=True).get(
                email=User.objects.normalize_email(email)
            )
        except User.DoesNotExist:
            return None

    def _create_signup_user(self, email: str, password: str) -> User:
        try:
            with transaction.atomic():
                user = self.create(email=email, password=password)
        except IntegrityError as error:
            if not self._is_email_taken(error):
                raise
            logger.info("signup_refused", reason="email_taken", user_id=self.get_id_by_email(email))
            raise EmailTakenError("An account with this email already exists.") from error
        logger.info("signup_succeeded", user_id=user.pk)
        return user

    # Postgres names unique=True's constraint <table>_<column>_key.
    def _is_email_taken(self, error: IntegrityError) -> bool:
        cause = error.__cause__
        return (
            isinstance(cause, UniqueViolation) and cause.diag.constraint_name == "users_email_key"
        )
