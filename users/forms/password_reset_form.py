from collections.abc import Iterator
from typing import Any

import structlog
from django.contrib.auth import forms as auth_forms

from users.models import User
from users.services.user_service import UserService

logger = structlog.get_logger(__name__)


class ConsumerPasswordResetForm(auth_forms.PasswordResetForm):
    # Like the consumer login, staff are kept out; they recover through the admin.
    def get_users(self, email: str) -> Iterator[User]:
        users = list(super().get_users(email))
        if not users:
            logger.info("password_reset_requested", user_id=None)
        for user in users:
            if user.is_privileged:
                logger.warning(
                    "password_reset_refused", reason="privileged_account", user_id=user.pk
                )
            else:
                yield user

    # Django's token is unused: the worker makes its own, so no token reaches the broker.
    def send_mail(
        self,
        subject_template_name: str,
        email_template_name: str,
        context: dict[str, Any],
        from_email: str | None,
        to_email: str,
        html_email_template_name: str | None = None,
    ) -> None:
        UserService().request_password_reset(context["user"].pk)
