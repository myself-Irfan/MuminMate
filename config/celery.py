import logging.config
import os
from typing import Any

from celery import Celery
from celery.signals import setup_logging
from django.conf import settings
from django_structlog.celery.steps import DjangoStructLogInitStep

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

app = Celery("config")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()
app.steps["worker"].add(DjangoStructLogInitStep)


# Connecting any receiver stops Celery from replacing our handlers with its own.
def apply_django_logging(**kwargs: Any) -> None:
    logging.config.dictConfig(settings.LOGGING)


setup_logging.connect(apply_django_logging)
