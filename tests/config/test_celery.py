import logging
import re

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


def test_every_task_routed_to_a_declared_queue() -> None:
    app.loader.import_default_modules()
    task_names = {name for name in app.tasks if not name.startswith("celery.")}
    declared = {queue.name for queue in app.conf.task_queues}

    routed = {name: app.conf.task_routes.get(name, {}).get("queue") for name in task_names}

    assert task_names
    assert set(routed.values()) <= declared


# Celery requires the default queue to be declared; it catches unrouted tasks.
def test_unrouted_task_goes_to_default_queue() -> None:
    route = app.amqp.router.route({}, "users.tasks.unrouted")

    assert route["queue"].name == "default"


def test_declared_queues_are_quorum_on_topic_exchanges() -> None:
    for queue in app.amqp.queues.values():
        assert queue.queue_arguments == {"x-queue-type": "quorum"}
        assert queue.exchange.type == "topic"


def test_every_queue_has_a_worker() -> None:
    compose = (settings.BASE_DIR / "compose.yaml").read_text()
    ci = (settings.BASE_DIR / ".github" / "workflows" / "ci.yml").read_text()
    declared = {queue.name for queue in app.conf.task_queues}

    compose_lists = re.findall(r'"worker", "-Q", "([^"]+)"', compose)
    ci_lists = re.findall(r"worker -Q (\S+)", ci)

    assert {name for names in compose_lists for name in names.split(",")} == declared
    assert {name for names in ci_lists for name in names.split(",")} == declared


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
