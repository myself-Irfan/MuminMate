from django.apps import AppConfig
from django_structlog.celery.signals import modify_context_before_task_publish
from django_structlog.signals import bind_extra_request_metadata

from core.signals import bind_client_ip, mark_health_probe, trim_task_context


class CoreConfig(AppConfig):
    name = "core"

    def ready(self) -> None:
        bind_extra_request_metadata.connect(bind_client_ip)
        bind_extra_request_metadata.connect(mark_health_probe)
        modify_context_before_task_publish.connect(trim_task_context)
