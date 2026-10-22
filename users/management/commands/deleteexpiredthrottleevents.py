from typing import Any

from django.core.management.base import BaseCommand

from users.services.login_failure_service import LoginFailureService
from users.services.request_limit_service import RequestLimitService


class Command(BaseCommand):
    help = "Delete throttle events older than the longest window of their limits."

    def handle(self, *args: Any, **options: Any) -> None:
        deleted = LoginFailureService().delete_expired() + RequestLimitService().delete_expired()
        self.stdout.write(f"Deleted {deleted} expired throttle events.")
