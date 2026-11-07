from django.conf import settings
from django.contrib.auth.base_user import AbstractBaseUser
from django.contrib.auth.models import PermissionsMixin
from django.db import models
from django.db.models.functions import Lower
from django.utils import timezone

from users.enums import EmploymentStatus, Gender, ThrottleScope
from users.managers import UserManager
from users.validators import (
    validate_birth_date_from_1900,
    validate_birth_date_not_in_future,
    validate_email_is_ascii,
)


class User(AbstractBaseUser, PermissionsMixin):
    email = models.EmailField(unique=True, validators=[validate_email_is_ascii])
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    date_joined = models.DateTimeField(default=timezone.now)
    email_verified_at = models.DateTimeField(null=True, blank=True)

    objects = UserManager()

    USERNAME_FIELD = "email"

    class Meta:
        db_table = "users"
        constraints = (
            models.CheckConstraint(
                condition=models.Q(email=Lower("email")) & ~models.Q(email__regex=r"\s"),
                name="users_email_normalized",
                violation_error_message="Email must be lowercase, without spaces.",
            ),
            models.CheckConstraint(
                condition=models.Q(email__regex=r"^[\x00-\x7f]*$"),
                name="users_email_ascii",
                violation_error_message="Email must use only ASCII characters.",
            ),
            models.CheckConstraint(
                condition=~models.Q(is_superuser=True, is_staff=False),
                name="users_is_superuser_requires_staff",
                violation_error_message="A superuser must also be staff.",
            ),
        )

    def __str__(self) -> str:
        return self.email

    def clean(self) -> None:
        super().clean()
        self.email = type(self).objects.normalize_email(self.email)

    @property
    def is_email_verified(self) -> bool:
        return self.email_verified_at is not None

    @property
    def is_privileged(self) -> bool:
        return self.is_staff or self.is_superuser

    @property
    def can_reset_password(self) -> bool:
        return self.is_active and not self.is_privileged and self.has_usable_password()

    @property
    def is_invite_pending(self) -> bool:
        return self.is_active and not self.has_usable_password()

    @property
    def is_verification_pending(self) -> bool:
        return self.is_active and not self.is_email_verified


class ThrottleEvent(models.Model):
    scope = models.CharField(max_length=32, choices=ThrottleScope)
    # Empty for scopes that count per IP only (Django: "" not null for strings).
    email_digest = models.CharField(max_length=64, blank=True)
    # Null when there is no client IP: no request, or a per-email-only scope.
    ip = models.GenericIPAddressField(null=True)
    # Set for scopes counted per account: the id survives an email change; an email key doesn't.
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, related_name="+"
    )
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "throttle_events"
        indexes = (
            models.Index(
                fields=("scope", "email_digest", "created_at"), name="throttle_events_digest_idx"
            ),
            models.Index(fields=("scope", "ip", "created_at"), name="throttle_events_ip_idx"),
        )
        constraints = (
            models.CheckConstraint(
                condition=models.Q(scope__in=ThrottleScope.values),
                name="throttle_events_scope_valid",
                violation_error_message="Unknown throttle scope.",
            ),
        )

    def __str__(self) -> str:
        return f"{self.get_scope_display()} at {self.created_at} from {self.ip}"


class Profile(models.Model):
    display_name = models.CharField(max_length=150)
    birth_date = models.DateField(
        validators=[validate_birth_date_not_in_future, validate_birth_date_from_1900]
    )
    gender = models.CharField(max_length=16, choices=Gender, blank=True)
    employment_status = models.CharField(max_length=32, choices=EmploymentStatus, blank=True)
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)

    class Meta:
        db_table = "profiles"
        constraints = (
            models.CheckConstraint(
                condition=models.Q(display_name__regex=r"\S"),
                name="profiles_display_name_not_blank",
                violation_error_message="Enter a name.",
            ),
            models.CheckConstraint(
                condition=models.Q(gender__in=["", *Gender.values]),
                name="profiles_gender_valid",
                violation_error_message="Unknown gender.",
            ),
            models.CheckConstraint(
                condition=models.Q(employment_status__in=["", *EmploymentStatus.values]),
                name="profiles_employment_status_valid",
                violation_error_message="Unknown employment status.",
            ),
        )

    def __str__(self) -> str:
        return self.display_name
