from users.models import User
from users.services.email_verification_service import EmailVerificationService
from users.services.invite_service import InviteService


class EmailChangeService:
    # The invite (any role) sets the password and confirms; /admin/ never checks verification.
    def request_confirmation(self, user: User) -> None:
        if user.is_invite_pending:
            InviteService().resend(user.pk)
            return
        if user.is_privileged:
            return
        EmailVerificationService().reset_verification(user)
