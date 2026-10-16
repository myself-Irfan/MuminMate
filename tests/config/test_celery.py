import logging

import pytest
from celery.app.defaults import SETTING_KEYS
from celery.signals import setup_logging
from django.conf import settings
from django_structlog.celery.steps import DjangoStructLogInitStep

from config.celery import app


def test_every_celery_setting_is_known_to_celery() -> None:
    names = {
        name.removeprefix("CELERY_").lower() for name in dir(settings) if name.startswith("CELERY_")
    }

    assert names - SETTING_KEYS == set()


def test_celery_broker_url_from_settings() -> None:
    assert app.conf.broker_url == settings.CELERY_BROKER_URL


def test_queues_are_quorum() -> None:
    assert app.conf.task_default_queue_type == "quorum"


def test_exchange_supports_native_delayed_delivery() -> None:
    assert app.conf.task_default_exchange_type == "topic"


def test_publish_waits_for_broker_confirm() -> None:
    assert app.conf.broker_transport_options["confirm_publish"] is True


def test_control_and_event_queues_are_exclusive() -> None:
    assert (app.conf.control_queue_exclusive, app.conf.event_queue_exclusive) == (True, True)


def test_celery_accepts_only_json() -> None:
    assert set(app.conf.accept_content) == {"json"}


def test_worker_runs_structlog_step() -> None:
    assert DjangoStructLogInitStep in app.steps["worker"]


@pytest.mark.usefixtures("restore_logging")
def test_worker_logging_uses_django_logging() -> None:
    logging.getLogger().handlers.clear()

    setup_logging.send(sender=None)

    assert [handler.name for handler in logging.getLogger().handlers] == ["stdout"]
