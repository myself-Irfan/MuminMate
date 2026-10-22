from datetime import timedelta

import structlog
from django.conf import settings
from django.db.models import Count, Max, Q
from django.utils import timezone

from users.enums import ThrottleScope
from users.limits import PasswordResetLimits, SignupLimits, VerificationEmailLimits
from users.models import ThrottleEvent
from users.throttling import digest_email, mask_ip

logger = structlog.get_logger(__name__)


# record_* insert, then count with their own row, so parallel requests can't all pass.
class RequestLimitService:
    def record_password_reset(self, email: str, ip: str | None) -> bool:
        limits = settings.THROTTLE_LIMITS.password_reset
        event = self._create(ThrottleScope.PASSWORD_RESET, email, ip)
        if self._is_email_limited(event, limits) or self._is_ip_limited(event, limits):
            return self._refuse(event)
        return True

    def record_signup(self, ip: str | None) -> bool:
        if ip is None:
            return True
        event = self._create(ThrottleScope.SIGNUP, None, ip)
        if self._is_ip_limited(event, settings.THROTTLE_LIMITS.signup):
            return self._refuse(event)
        return True

    def record_verification_email(self, email: str) -> bool:
        event = self._create(ThrottleScope.VERIFICATION_EMAIL, email, None)
        if self._is_email_limited(event, settings.THROTTLE_LIMITS.verification_email):
            return self._refuse(event)
        return True

    def record(self, scope: ThrottleScope, email: str, ip: str | None) -> ThrottleEvent:
        return self._create(scope, email, ip)

    # Rows past their scope's longest window only hold personal data.
    def delete_expired(self) -> int:
        limits = settings.THROTTLE_LIMITS
        now = timezone.now()
        reset_window = max(
            limits.password_reset.email_window_seconds, limits.password_reset.ip_window_seconds
        )
        expired = (
            Q(
                scope=ThrottleScope.PASSWORD_RESET,
                created_at__lt=now - timedelta(seconds=reset_window),
            )
            | Q(
                scope=ThrottleScope.SIGNUP,
                created_at__lt=now - timedelta(seconds=limits.signup.ip_window_seconds),
            )
            | Q(
                scope=ThrottleScope.VERIFICATION_EMAIL,
                created_at__lt=now
                - timedelta(seconds=limits.verification_email.email_window_seconds),
            )
        )
        deleted, _ = ThrottleEvent.objects.filter(expired).delete()
        return deleted

    def _create(self, scope: ThrottleScope, email: str | None, ip: str | None) -> ThrottleEvent:
        return ThrottleEvent.objects.create(
            scope=scope,
            email_digest=digest_email(email) if email is not None else "",
            ip=mask_ip(ip) if ip is not None else None,
        )

    def _refuse(self, event: ThrottleEvent) -> bool:
        event.delete()
        logger.warning("request_limited", scope=event.scope)
        return False

    def _is_email_limited(
        self, event: ThrottleEvent, limits: PasswordResetLimits | VerificationEmailLimits
    ) -> bool:
        recent = ThrottleEvent.objects.filter(
            scope=event.scope,
            email_digest=event.email_digest,
            created_at__gte=event.created_at - timedelta(seconds=limits.email_window_seconds),
        ).aggregate(count=Count("id"), last_at=Max("created_at", filter=~Q(pk=event.pk)))
        if recent["count"] > limits.email_max_events:
            return True
        last_at = recent["last_at"]
        return last_at is not None and event.created_at - last_at < timedelta(
            seconds=limits.email_cooldown_seconds
        )

    # Without an IP there is nothing to count.
    def _is_ip_limited(
        self, event: ThrottleEvent, limits: PasswordResetLimits | SignupLimits
    ) -> bool:
        if event.ip is None:
            return False
        recent = ThrottleEvent.objects.filter(
            scope=event.scope,
            ip=event.ip,
            created_at__gte=event.created_at - timedelta(seconds=limits.ip_window_seconds),
        ).count()
        return recent > limits.ip_max_events
