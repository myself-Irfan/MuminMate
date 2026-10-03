from typing import Any

from django.core.management.base import BaseCommand

from users.services import delete_expired_login_failures


class Command(BaseCommand):
    help = "Delete login failures older than the longest login-limit window."

    def handle(self, *args: Any, **options: Any) -> None:
        deleted = delete_expired_login_failures()
        self.stdout.write(f"Deleted {deleted} expired login failures.")
