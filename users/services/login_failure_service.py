from dataclasses import dataclass
from datetime import datetime, timedelta

from django.conf import settings
from django.db.models import Count, Max, Q, QuerySet
from django.utils import timezone

from users.enums import ThrottleScope
from users.limits import LoginLimits
from users.models import ThrottleEvent
from users.services.request_limit_service import RequestLimitService
from users.throttling import digest_email, mask_ip


class LoginFailureService:
    @dataclass(frozen=True)
    class RecentFailures:
        email: int
        email_last_failed_at: datetime | None
        email_ip: int
        ip: int

    # Saved before the hash and counted with itself, so parallel guesses can't all pass.
    def record_attempt(self, email: str, ip: str | None) -> ThrottleEvent | None:
        attempt = RequestLimitService().record(ThrottleScope.LOGIN_FAILURE, email, ip)
        if self._is_throttled(attempt):
            attempt.delete()
            return None
        return attempt

    # Pair only: one known password mustn't reset IP or email history.
    def clear_attempt(self, attempt: ThrottleEvent) -> None:
        if attempt.ip is None:
            attempt.delete()
            return
        self._failures().filter(email_digest=attempt.email_digest, ip=attempt.ip).delete()

    def clear(self, email: str, ip: str | None) -> None:
        if ip is None:
            return
        self._failures().filter(email_digest=digest_email(email), ip=mask_ip(ip)).delete()

    # Rows past every window only hold personal data.
    def delete_expired(self) -> int:
        limits = settings.THROTTLE_LIMITS.login
        longest_window = max(
            limits.email_ip_window_seconds, limits.ip_window_seconds, limits.email_window_seconds
        )
        cutoff = timezone.now() - timedelta(seconds=longest_window)
        deleted, _ = self._failures().filter(created_at__lt=cutoff).delete()
        return deleted

    def _is_throttled(self, attempt: ThrottleEvent) -> bool:
        limits = settings.THROTTLE_LIMITS.login
        failures = self._count_recent(attempt, limits)
        if failures.email_ip > limits.email_ip_max_events or failures.ip > limits.ip_max_events:
            return True
        return self._is_email_backing_off(failures, limits, attempt.created_at)

    def _count_recent(self, attempt: ThrottleEvent, limits: LoginLimits) -> RecentFailures:
        now = attempt.created_at
        from_email = Q(email_digest=attempt.email_digest)
        # Without an IP this matches nothing, so the IP rules count 0.
        from_ip = Q(ip=attempt.ip) if attempt.ip is not None else Q(pk__in=[])
        email_rule = from_email & self._within(limits.email_window_seconds, now)
        email_ip_rule = from_email & from_ip & self._within(limits.email_ip_window_seconds, now)
        ip_rule = from_ip & self._within(limits.ip_window_seconds, now)
        row = (
            self._failures()
            .filter(from_email | from_ip)
            .aggregate(
                email=Count("id", filter=email_rule),
                email_last_failed_at=Max("created_at", filter=email_rule & ~Q(pk=attempt.pk)),
                email_ip=Count("id", filter=email_ip_rule),
                ip=Count("id", filter=ip_rule),
            )
        )
        return self.RecentFailures(**row)

    def _failures(self) -> QuerySet[ThrottleEvent]:
        return ThrottleEvent.objects.filter(scope=ThrottleScope.LOGIN_FAILURE)

    def _within(self, window_seconds: int, now: datetime) -> Q:
        return Q(created_at__gte=now - timedelta(seconds=window_seconds))

    # Past the limit: one attempt per backoff, not a permanent lock.
    def _is_email_backing_off(
        self, failures: RecentFailures, limits: LoginLimits, now: datetime
    ) -> bool:
        if failures.email <= limits.email_max_events or failures.email_last_failed_at is None:
            return False
        return now - failures.email_last_failed_at < timedelta(seconds=limits.email_backoff_seconds)
