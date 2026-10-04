from datetime import timedelta
from io import StringIO

import pytest
from django.core.management import CommandError, call_command
from django.utils import timezone

from users.models import LoginFailure, User


@pytest.mark.django_db
def test_createsuperuser_by_email(monkeypatch: pytest.MonkeyPatch, password: str) -> None:
    monkeypatch.setenv("DJANGO_SUPERUSER_PASSWORD", password)

    call_command("createsuperuser", "--noinput", email="Admin@Example.com", stdout=StringIO())

    user = User.objects.get(email="admin@example.com")
    assert user.is_staff
    assert user.is_superuser
    assert user.check_password(password)


@pytest.mark.django_db
def test_createsuperuser_fails_when_email_not_ascii(
    monkeypatch: pytest.MonkeyPatch, password: str
) -> None:
    monkeypatch.setenv("DJANGO_SUPERUSER_PASSWORD", password)

    with pytest.raises(CommandError, match="ASCII"):
        call_command(
            "createsuperuser", "--noinput", email="\u0131rfan@example.com", stdout=StringIO()
        )

    assert not User.objects.exists()


# Django validates only interactively; --noinput trusts the operator.
@pytest.mark.django_db
def test_createsuperuser_noinput_skips_password_validation(
    monkeypatch: pytest.MonkeyPatch, short_password: str
) -> None:
    monkeypatch.setenv("DJANGO_SUPERUSER_PASSWORD", short_password)

    call_command("createsuperuser", "--noinput", email="admin@example.com", stdout=StringIO())

    assert User.objects.get(email="admin@example.com").check_password(short_password)


@pytest.mark.django_db
@pytest.mark.usefixtures("login_limits")
def test_deleteexpiredloginfailures_reports_deleted_count() -> None:
    LoginFailure.objects.create(
        email_digest="old", failed_at=timezone.now() - timedelta(seconds=301)
    )
    stdout = StringIO()

    call_command("deleteexpiredloginfailures", stdout=stdout)

    assert stdout.getvalue() == "Deleted 1 expired login failures.\n"
    assert not LoginFailure.objects.exists()
