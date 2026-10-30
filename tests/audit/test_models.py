import pytest
from django.db import IntegrityError, connections
from django.utils import timezone

from audit.enums import EventType
from audit.models import IncomingRequestResponseEvent


def create_event(**fields: object) -> IncomingRequestResponseEvent:
    return IncomingRequestResponseEvent.objects.create(
        **{
            "type": EventType.REQUEST,
            "request_id": "req-1",
            "method": "GET",
            "path": "/",
            "logged_at": timezone.now(),
            **fields,
        }
    )


@pytest.mark.django_db(databases=["default", "log"])
def test_event_saved_in_log_database_only() -> None:
    event = create_event()

    table = IncomingRequestResponseEvent._meta.db_table
    assert event._state.db == "log"
    assert table in connections["log"].introspection.table_names()
    assert table not in connections["default"].introspection.table_names()


@pytest.mark.django_db(databases=["log"])
def test_event_type_outside_choices_refused_by_db() -> None:
    with pytest.raises(IntegrityError, match="incoming_request_response_events_type_valid"):
        create_event(type="OTHER")


def test_event_str_shows_type_method_path_and_request_id() -> None:
    event = IncomingRequestResponseEvent(
        type=EventType.REQUEST, method="GET", path="/accounts/login/", request_id="req-1"
    )

    assert str(event) == "REQUEST GET /accounts/login/ (req-1)"
