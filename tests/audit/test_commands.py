from io import StringIO
from unittest.mock import Mock

import pytest
from django.core.management import call_command


def test_deleteexpiredauditevents_reports_deleted_count(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "audit.management.commands.deleteexpiredauditevents.AuditEventService.delete_expired",
        Mock(return_value=3),
    )
    stdout = StringIO()

    call_command("deleteexpiredauditevents", stdout=stdout)

    assert stdout.getvalue() == "Deleted 3 expired audit events.\n"
