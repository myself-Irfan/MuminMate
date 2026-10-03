from dataclasses import dataclass
from datetime import datetime, timedelta

from django.conf import settings
from django.db.models import Count, Max, Q
from django.utils import timezone

from users.limits import EmailLoginLimit, LoginLimit, LoginLimits
from users.models import LoginFailure
from users.throttling import digest_email, mask_ip


@dataclass(frozen=True)
class RecentFailures:
    email: int
    email_last_failed_at: datetime | None
    email_ip: int
    ip: int


def is_login_throttled(email: str, ip: str | None) -> bool:
    limits = settings.LOGIN_LIMITS
    now = timezone.now()
    failures = _count_recent_failures(email, ip, limits, now)
    if failures.email_ip >= limits.email_ip.max_failures or failures.ip >= limits.ip.max_failures:
        return True
    return _is_email_backing_off(failures, limits.email, now)


def _count_recent_failures(
    email: str, ip: str | None, limits: LoginLimits, now: datetime
) -> RecentFailures:
    from_email = Q(email_digest=digest_email(email))
    # Without an IP this matches nothing, so the IP rules count 0.
    from_ip = Q(ip=mask_ip(ip)) if ip is not None else Q(pk__in=[])
    email_rule = from_email & _within(limits.email, now)
    email_ip_rule = from_email & from_ip & _within(limits.email_ip, now)
    ip_rule = from_ip & _within(limits.ip, now)
    row = LoginFailure.objects.filter(from_email | from_ip).aggregate(
        email=Count("id", filter=email_rule),
        email_last_failed_at=Max("failed_at", filter=email_rule),
        email_ip=Count("id", filter=email_ip_rule),
        ip=Count("id", filter=ip_rule),
    )
    return RecentFailures(**row)


def _within(limit: LoginLimit, now: datetime) -> Q:
    return Q(failed_at__gte=now - timedelta(seconds=limit.window_seconds))


# Past the limit: one attempt per backoff, not a permanent lock.
def _is_email_backing_off(failures: RecentFailures, limit: EmailLoginLimit, now: datetime) -> bool:
    if failures.email < limit.max_failures or failures.email_last_failed_at is None:
        return False
    return now - failures.email_last_failed_at < timedelta(seconds=limit.backoff_seconds)
