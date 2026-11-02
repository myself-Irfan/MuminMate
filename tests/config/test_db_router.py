import pytest
from django.db import router

from audit.models import IncomingRequestResponseEvent
from users.models import User


def test_audit_models_use_log_database() -> None:
    model = IncomingRequestResponseEvent
    assert (router.db_for_read(model), router.db_for_write(model)) == ("log", "log")


def test_other_models_use_default_database() -> None:
    assert (router.db_for_read(User), router.db_for_write(User)) == ("default", "default")


@pytest.mark.parametrize(
    ("db", "app_label", "allowed"),
    [
        ("log", "audit", True),
        ("default", "audit", False),
        ("log", "users", False),
        ("default", "users", True),
    ],
)
def test_migrations_keep_each_app_in_its_database(db: str, app_label: str, allowed: bool) -> None:
    assert router.allow_migrate(db, app_label) is allowed


def test_relation_refused_across_databases() -> None:
    assert router.allow_relation(IncomingRequestResponseEvent(), User()) is False


def test_relation_allowed_within_default_database() -> None:
    assert router.allow_relation(User(), User()) is True
