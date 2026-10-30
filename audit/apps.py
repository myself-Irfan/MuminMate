from django.apps import AppConfig
from django.contrib.auth.signals import user_logged_out
from django.core.signals import got_request_exception

from audit import signals


class AuditConfig(AppConfig):
    name = "audit"

    def ready(self) -> None:
        got_request_exception.connect(signals.remember_request_error)
        user_logged_out.connect(signals.remember_logged_out_user)
