import unicodedata
from typing import Any

from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager


class UserManager[T: AbstractBaseUser](BaseUserManager[T]):
    @classmethod
    def normalize_email(cls, email: str | None) -> str:
        # NFKC as Django's login form does; Django's default lowercases only the domain.
        return unicodedata.normalize("NFKC", email or "").strip().lower()

    def get_by_natural_key(self, username: str | None) -> T:
        return self.get(email=self.normalize_email(username))

    async def aget_by_natural_key(self, username: str | None) -> T:
        return await self.aget(email=self.normalize_email(username))

    def create_user(self, email: str, password: str | None = None, **extra_fields: Any) -> T:
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email: str, password: str | None = None, **extra_fields: Any) -> T:
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        if extra_fields["is_staff"] is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields["is_superuser"] is not True:
            raise ValueError("Superuser must have is_superuser=True.")
        return self._create_user(email, password, **extra_fields)

    def _create_user(self, email: str, password: str | None, **extra_fields: Any) -> T:
        email = self.normalize_email(email)
        if not email:
            raise ValueError("The email must be set.")
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user
