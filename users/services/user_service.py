from functools import partial

import structlog
from django.db import IntegrityError, transaction
from kombu.exceptions import OperationalError
from psycopg.errors import UniqueViolation

from users.exceptions import EmailTakenError
from users.models import User
from users.tasks import send_password_reset_email, send_signup_email

logger = structlog.get_logger(__name__)


class UserService:
    def create(self, *, email: str, password: str | None, is_staff: bool = False) -> User:
        return User.objects.create_user(email=email, password=password, is_staff=is_staff)

    def signup(self, *, email: str, password: str) -> None:
        user_id = self._create_signup_user(email, password)
        transaction.on_commit(partial(self._queue_signup_email, user_id))

    def request_password_reset(self, user_id: int) -> None:
        logger.info("password_reset_requested", user_id=user_id)
        transaction.on_commit(partial(self._queue_password_reset_email, user_id))

    def get_id_by_email(self, email: str) -> int | None:
        try:
            return User.objects.values_list("pk", flat=True).get(
                email=User.objects.normalize_email(email)
            )
        except User.DoesNotExist:
            return None

    def _create_signup_user(self, email: str, password: str) -> int:
        try:
            with transaction.atomic():
                user = self.create(email=email, password=password)
        except IntegrityError as error:
            if not self._is_email_taken(error):
                raise
            logger.info("signup_refused", reason="email_taken", user_id=self.get_id_by_email(email))
            raise EmailTakenError("An account with this email already exists.") from error
        logger.info("signup_succeeded", user_id=user.pk)
        return user.pk

    # A broker outage mustn't fail the request, as with Django's own password reset send_mail.
    def _queue_signup_email(self, user_id: int) -> None:
        try:
            send_signup_email.delay(user_id)
        except OperationalError:
            logger.exception("signup_email_queue_failed", user_id=user_id)

    def _queue_password_reset_email(self, user_id: int) -> None:
        try:
            send_password_reset_email.delay(user_id)
        except OperationalError:
            logger.exception("password_reset_email_queue_failed", user_id=user_id)

    # Postgres names unique=True's constraint <table>_<column>_key.
    def _is_email_taken(self, error: IntegrityError) -> bool:
        cause = error.__cause__
        return (
            isinstance(cause, UniqueViolation) and cause.diag.constraint_name == "users_email_key"
        )
