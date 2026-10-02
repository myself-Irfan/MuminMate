from django.apps import AppConfig
from django.contrib.auth.signals import user_logged_in

from users.signals import record_login_time


class UsersConfig(AppConfig):
    name = "users"

    def ready(self) -> None:
        user_logged_in.connect(record_login_time)
