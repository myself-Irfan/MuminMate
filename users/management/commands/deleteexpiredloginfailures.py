from typing import Any

from django.core.management.base import BaseCommand

from users.services.login_failure_service import LoginFailureService


class Command(BaseCommand):
    help = "Delete login failures older than the longest login-limit window."

    def handle(self, *args: Any, **options: Any) -> None:
        deleted = LoginFailureService().delete_expired()
        self.stdout.write(f"Deleted {deleted} expired login failures.")
