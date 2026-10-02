from io import StringIO

import pytest
from django.core.management import call_command

from users.models import User


@pytest.mark.django_db
def test_createsuperuser_by_email(monkeypatch: pytest.MonkeyPatch, password: str) -> None:
    monkeypatch.setenv("DJANGO_SUPERUSER_PASSWORD", password)

    call_command("createsuperuser", "--noinput", email="Admin@Example.com", stdout=StringIO())

    user = User.objects.get(email="admin@example.com")
    assert user.is_staff
    assert user.is_superuser
    assert user.check_password(password)


# Django validates only interactively; --noinput trusts the operator.
@pytest.mark.django_db
def test_createsuperuser_noinput_skips_password_validation(
    monkeypatch: pytest.MonkeyPatch, short_password: str
) -> None:
    monkeypatch.setenv("DJANGO_SUPERUSER_PASSWORD", short_password)

    call_command("createsuperuser", "--noinput", email="admin@example.com", stdout=StringIO())

    assert User.objects.get(email="admin@example.com").check_password(short_password)
