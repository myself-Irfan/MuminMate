from django.contrib.auth.base_user import AbstractBaseUser
from django.contrib.auth.models import PermissionsMixin
from django.db import models
from django.db.models.functions import Lower
from django.utils import timezone

from users.managers import UserManager


class User(AbstractBaseUser, PermissionsMixin):
    email = models.EmailField(unique=True)
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


class LoginFailure(models.Model):
    email_digest = models.CharField(max_length=64)
    # Null when authenticate() has no request.
    ip = models.GenericIPAddressField(null=True)
    failed_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "login_failures"
        indexes = (
            models.Index(fields=("email_digest", "failed_at"), name="login_failures_digest_idx"),
            models.Index(fields=("ip", "failed_at"), name="login_failures_ip_idx"),
        )

    def __str__(self) -> str:
        return f"Login failure at {self.failed_at} from {self.ip}"
