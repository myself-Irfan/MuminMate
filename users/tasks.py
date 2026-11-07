from celery import shared_task
from celery.exceptions import SoftTimeLimitExceeded

from users.services.email_service import EmailService


# Retried with full jitter: 0-1, 0-2, 0-4, 0-8, 0-10 min.
@shared_task(
    autoretry_for=(OSError, SoftTimeLimitExceeded),
    retry_backoff=60,
    retry_backoff_max=600,
    max_retries=5,
    soft_time_limit=30,
    time_limit=60,
)
def send_verification_email(user_id: int) -> None:
    EmailService().send_verification_email(user_id)


@shared_task(
    autoretry_for=(OSError, SoftTimeLimitExceeded),
    retry_backoff=60,
    retry_backoff_max=600,
    max_retries=5,
    soft_time_limit=30,
    time_limit=60,
)
def send_password_reset_email(user_id: int) -> None:
    EmailService().send_password_reset_email(user_id)


@shared_task(
    autoretry_for=(OSError, SoftTimeLimitExceeded),
    retry_backoff=60,
    retry_backoff_max=600,
    max_retries=5,
    soft_time_limit=30,
    time_limit=60,
)
def send_invite_email(user_id: int) -> None:
    EmailService().send_invite_email(user_id)


@shared_task(
    autoretry_for=(OSError, SoftTimeLimitExceeded),
    retry_backoff=60,
    retry_backoff_max=600,
    max_retries=5,
    soft_time_limit=30,
    time_limit=60,
)
def send_password_changed_email(user_id: int) -> None:
    EmailService().send_password_changed_email(user_id)


@shared_task(
    autoretry_for=(OSError, SoftTimeLimitExceeded),
    retry_backoff=60,
    retry_backoff_max=600,
    max_retries=5,
    soft_time_limit=30,
    time_limit=60,
)
def send_email_changed_notice(user_id: int, old_email: str) -> None:
    EmailService().send_email_changed_notice(user_id, old_email)


@shared_task(
    autoretry_for=(OSError, SoftTimeLimitExceeded),
    retry_backoff=60,
    retry_backoff_max=600,
    max_retries=5,
    soft_time_limit=30,
    time_limit=60,
)
def send_email_change_link(user_id: int, new_email: str) -> None:
    EmailService().send_email_change_link(user_id, new_email)
