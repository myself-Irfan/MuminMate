from django.apps import AppConfig
from django_structlog.signals import bind_extra_request_metadata

from core.signals import bind_client_ip, mark_health_probe


class CoreConfig(AppConfig):
    name = "core"

    def ready(self) -> None:
        bind_extra_request_metadata.connect(bind_client_ip)
        bind_extra_request_metadata.connect(mark_health_probe)
