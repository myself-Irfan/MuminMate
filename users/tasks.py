from smtplib import SMTPAuthenticationError, SMTPRecipientsRefused, SMTPSenderRefused

from celery import shared_task
from celery.exceptions import SoftTimeLimitExceeded

from users.services.email_service import EmailService


# Retried with full jitter: 0-1, 0-2, 0-4, 0-8, 0-10 min.
@shared_task(
    autoretry_for=(OSError, SoftTimeLimitExceeded),
    dont_autoretry_for=(SMTPRecipientsRefused, SMTPSenderRefused, SMTPAuthenticationError),
    retry_backoff=60,
    retry_backoff_max=600,
    max_retries=5,
    soft_time_limit=30,
    time_limit=60,
)
def send_signup_email(user_id: int) -> None:
    EmailService().send_signup_email(user_id)


@shared_task(
    autoretry_for=(OSError, SoftTimeLimitExceeded),
    dont_autoretry_for=(SMTPRecipientsRefused, SMTPSenderRefused, SMTPAuthenticationError),
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
    dont_autoretry_for=(SMTPRecipientsRefused, SMTPSenderRefused, SMTPAuthenticationError),
    retry_backoff=60,
    retry_backoff_max=600,
    max_retries=5,
    soft_time_limit=30,
    time_limit=60,
)
def send_already_verified_email(user_id: int) -> None:
    EmailService().send_already_verified_email(user_id)


@shared_task(
    autoretry_for=(OSError, SoftTimeLimitExceeded),
    dont_autoretry_for=(SMTPRecipientsRefused, SMTPSenderRefused, SMTPAuthenticationError),
    retry_backoff=60,
    retry_backoff_max=600,
    max_retries=5,
    soft_time_limit=30,
    time_limit=60,
)
def send_invite_email(user_id: int) -> None:
    EmailService().send_invite_email(user_id)
