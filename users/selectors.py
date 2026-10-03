import ipaddress
from datetime import datetime, timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db.models import Count, Max, QuerySet
from django.utils import timezone
from django.utils.crypto import salted_hmac

from config.env import EmailLoginLimit, LoginLimit
from users.models import LoginFailure


def digest_email(email: str) -> str:
    normalized = get_user_model().objects.normalize_email(email)
    return salted_hmac("users.login_failure", normalized, algorithm="sha256").hexdigest()


def mask_ip(address: str) -> str:
    ip = ipaddress.ip_address(address)
    if isinstance(ip, ipaddress.IPv4Address):
        return str(ip)
    if ip.ipv4_mapped:
        return str(ip.ipv4_mapped)
    # One IPv6 subscriber usually holds a whole /64.
    return str(ipaddress.ip_network(f"{ip}/64", strict=False).network_address)


def is_login_throttled(email: str, ip: str | None) -> bool:
    limits = settings.LOGIN_LIMITS
    now = timezone.now()
    email_failures = LoginFailure.objects.filter(email_digest=digest_email(email))
    if ip is not None:
        masked_ip = mask_ip(ip)
        if _has_reached(email_failures.filter(ip=masked_ip), limits.email_ip, now):
            return True
        if _has_reached(LoginFailure.objects.filter(ip=masked_ip), limits.ip, now):
            return True
    return _is_email_backing_off(email_failures, limits.email, now)


def _has_reached(failures: QuerySet[LoginFailure], limit: LoginLimit, now: datetime) -> bool:
    since = now - timedelta(seconds=limit.window_seconds)
    return failures.filter(failed_at__gte=since).count() >= limit.max_failures


# Past the limit: one attempt per backoff, not a permanent lock.
def _is_email_backing_off(
    failures: QuerySet[LoginFailure], limit: EmailLoginLimit, now: datetime
) -> bool:
    since = now - timedelta(seconds=limit.window_seconds)
    window = failures.filter(failed_at__gte=since).aggregate(
        count=Count("id"), last_failed_at=Max("failed_at")
    )
    count: int = window["count"]
    if count < limit.max_failures:
        return False
    last_failed_at: datetime = window["last_failed_at"]
    return now - last_failed_at < timedelta(seconds=limit.backoff_seconds)
