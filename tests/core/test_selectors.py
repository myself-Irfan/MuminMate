from unittest.mock import Mock

import pytest
from django.db import OperationalError, connection
from django.db.migrations.executor import MigrationExecutor

from core.selectors import is_db_ready


@pytest.mark.django_db
def test_is_db_ready_when_connected() -> None:
    assert is_db_ready() is True


@pytest.mark.django_db
def test_is_db_ready_when_connection_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(connection, "cursor", Mock(side_effect=OperationalError))

    assert is_db_ready() is False


@pytest.mark.django_db
def test_is_db_ready_with_pending_migrations(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(MigrationExecutor, "migration_plan", Mock(return_value=[("app", False)]))

    assert is_db_ready() is False
