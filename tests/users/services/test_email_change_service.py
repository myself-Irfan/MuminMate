from unittest.mock import Mock

import pytest

from users.models import User
from users.services.email_change_service import EmailChangeService


@pytest.fixture
def invite_resend(monkeypatch: pytest.MonkeyPatch) -> Mock:
    resend = Mock()
    monkeypatch.setattr("users.services.email_change_service.InviteService.resend", resend)
    return resend


@pytest.fixture
def verification_reset(monkeypatch: pytest.MonkeyPatch) -> Mock:
    reset = Mock()
    monkeypatch.setattr(
        "users.services.email_change_service.EmailVerificationService.reset_verification", reset
    )
    return reset


# The old invite link dies with the old address; the new one confirms the email too.
def test_request_confirmation_resends_invite_when_invite_pending(
    invite_resend: Mock, verification_reset: Mock, invited_user: User
) -> None:
    EmailChangeService().request_confirmation(invited_user)

    invite_resend.assert_called_once_with(invited_user.pk)
    verification_reset.assert_not_called()


def test_request_confirmation_resets_verification_when_password_set(
    invite_resend: Mock, verification_reset: Mock, consumer_user: User
) -> None:
    EmailChangeService().request_confirmation(consumer_user)

    verification_reset.assert_called_once_with(consumer_user)
    invite_resend.assert_not_called()


def test_request_confirmation_resends_invite_when_staff_invite_pending(
    invite_resend: Mock, verification_reset: Mock, invited_user: User
) -> None:
    User.objects.filter(pk=invited_user.pk).update(is_staff=True)
    invited_user.refresh_from_db()

    EmailChangeService().request_confirmation(invited_user)

    invite_resend.assert_called_once_with(invited_user.pk)
    verification_reset.assert_not_called()


# Staff log in at /admin/, which never checks verification; a consumer link would mean nothing.
def test_request_confirmation_does_nothing_when_staff_has_password(
    invite_resend: Mock, verification_reset: Mock, staff_user: User
) -> None:
    EmailChangeService().request_confirmation(staff_user)

    invite_resend.assert_not_called()
    verification_reset.assert_not_called()
