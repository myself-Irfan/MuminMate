from datetime import timedelta
from io import StringIO

import pytest
from django.core.management import CommandError, call_command
from django.utils import timezone

from users.enums import ThrottleScope
from users.models import ThrottleEvent, User


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
def test_deleteexpiredthrottleevents_reports_deleted_count() -> None:
    ThrottleEvent.objects.create(
        scope=ThrottleScope.LOGIN_FAILURE,
        email_digest="old",
        created_at=timezone.now() - timedelta(seconds=301),
    )
    ThrottleEvent.objects.create(
        scope=ThrottleScope.PASSWORD_RESET,
        email_digest="old",
        created_at=timezone.now() - timedelta(days=1),
    )
    stdout = StringIO()

    call_command("deleteexpiredthrottleevents", stdout=stdout)

    assert stdout.getvalue() == "Deleted 2 expired throttle events.\n"
    assert not ThrottleEvent.objects.exists()


# Every scope, so a new one without a retention rule fails here.
@pytest.mark.django_db
@pytest.mark.usefixtures("login_limits", "request_limits")
@pytest.mark.parametrize("scope", ThrottleScope)
def test_deleteexpiredthrottleevents_deletes_old_rows_of_every_scope(scope: ThrottleScope) -> None:
    ThrottleEvent.objects.create(
        scope=scope, email_digest="old", created_at=timezone.now() - timedelta(days=1)
    )

    call_command("deleteexpiredthrottleevents", stdout=StringIO())

    assert not ThrottleEvent.objects.exists()
