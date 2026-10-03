from datetime import timedelta

from django.conf import settings
from django.utils import timezone

from users.models import LoginFailure
from users.throttling import digest_email, mask_ip


def record_login_failure(email: str, ip: str | None) -> None:
    LoginFailure.objects.create(
        email_digest=digest_email(email), ip=mask_ip(ip) if ip is not None else None
    )


# Pair only: one known password mustn't reset IP or email history.
def clear_login_failures(email: str, ip: str | None) -> None:
    if ip is None:
        return
    LoginFailure.objects.filter(email_digest=digest_email(email), ip=mask_ip(ip)).delete()


# Rows past every window only hold personal data.
def delete_expired_login_failures() -> int:
    limits = settings.LOGIN_LIMITS
    longest_window = max(rule.window_seconds for rule in (limits.email_ip, limits.ip, limits.email))
    cutoff = timezone.now() - timedelta(seconds=longest_window)
    deleted, _ = LoginFailure.objects.filter(failed_at__lt=cutoff).delete()
    return deleted
