from dataclasses import dataclass
from datetime import datetime, timedelta

from django.conf import settings
from django.db.models import Count, Max, Q
from django.utils import timezone

from users.limits import EmailLoginLimit, LoginLimit, LoginLimits
from users.models import LoginFailure
from users.throttling import digest_email, mask_ip


class LoginFailureService:
    @dataclass(frozen=True)
    class RecentFailures:
        email: int
        email_last_failed_at: datetime | None
        email_ip: int
        ip: int

    def is_throttled(self, email: str, ip: str | None) -> bool:
        limits = settings.LOGIN_LIMITS
        now = timezone.now()
        failures = self._count_recent(email, ip, limits, now)
        if (
            failures.email_ip >= limits.email_ip.max_failures
            or failures.ip >= limits.ip.max_failures
        ):
            return True
        return self._is_email_backing_off(failures, limits.email, now)

    def record(self, email: str, ip: str | None) -> None:
        LoginFailure.objects.create(
            email_digest=digest_email(email), ip=mask_ip(ip) if ip is not None else None
        )

    # Pair only: one known password mustn't reset IP or email history.
    def clear(self, email: str, ip: str | None) -> None:
        if ip is None:
            return
        LoginFailure.objects.filter(email_digest=digest_email(email), ip=mask_ip(ip)).delete()

    # Rows past every window only hold personal data.
    def delete_expired(self) -> int:
        limits = settings.LOGIN_LIMITS
        longest_window = max(
            rule.window_seconds for rule in (limits.email_ip, limits.ip, limits.email)
        )
        cutoff = timezone.now() - timedelta(seconds=longest_window)
        deleted, _ = LoginFailure.objects.filter(failed_at__lt=cutoff).delete()
        return deleted

    def _count_recent(
        self, email: str, ip: str | None, limits: LoginLimits, now: datetime
    ) -> RecentFailures:
        from_email = Q(email_digest=digest_email(email))
        # Without an IP this matches nothing, so the IP rules count 0.
        from_ip = Q(ip=mask_ip(ip)) if ip is not None else Q(pk__in=[])
        email_rule = from_email & self._within(limits.email, now)
        email_ip_rule = from_email & from_ip & self._within(limits.email_ip, now)
        ip_rule = from_ip & self._within(limits.ip, now)
        row = LoginFailure.objects.filter(from_email | from_ip).aggregate(
            email=Count("id", filter=email_rule),
            email_last_failed_at=Max("failed_at", filter=email_rule),
            email_ip=Count("id", filter=email_ip_rule),
            ip=Count("id", filter=ip_rule),
        )
        return self.RecentFailures(**row)

    def _within(self, limit: LoginLimit, now: datetime) -> Q:
        return Q(failed_at__gte=now - timedelta(seconds=limit.window_seconds))

    # Past the limit: one attempt per backoff, not a permanent lock.
    def _is_email_backing_off(
        self, failures: RecentFailures, limit: EmailLoginLimit, now: datetime
    ) -> bool:
        if failures.email < limit.max_failures or failures.email_last_failed_at is None:
            return False
        return now - failures.email_last_failed_at < timedelta(seconds=limit.backoff_seconds)
