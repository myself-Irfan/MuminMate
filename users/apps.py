from django.apps import AppConfig
from django.contrib.auth.signals import user_logged_in, user_logged_out

from users import signals


class UsersConfig(AppConfig):
    name = "users"

    def ready(self) -> None:
        user_logged_in.connect(signals.record_login_time)
        user_logged_in.connect(signals.log_login)
        user_logged_out.connect(signals.log_logout)
