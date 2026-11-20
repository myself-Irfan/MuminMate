import pytest
from django.db import IntegrityError, connections
from django.utils import timezone

from audit.enums import EventType, Partner
from audit.models import IncomingRequestResponseEvent, OutgoingRequestResponseEvent


def create_incoming_event(**fields: object) -> IncomingRequestResponseEvent:
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


def create_outgoing_event(**fields: object) -> OutgoingRequestResponseEvent:
    return OutgoingRequestResponseEvent.objects.create(
        **{
            "type": EventType.REQUEST,
            "request_id": "req-1",
            "partner": Partner.EMAIL,
            "name": "password_reset",
            "method": "SMTP",
            "url": "smtp://mailpit:1025",
            "logged_at": timezone.now(),
            **fields,
        }
    )


@pytest.mark.django_db(databases=["default", "log"])
def test_incoming_event_saved_in_log_database_only() -> None:
    event = create_incoming_event()

    table = IncomingRequestResponseEvent._meta.db_table
    assert event._state.db == "log"
    assert table in connections["log"].introspection.table_names()
    assert table not in connections["default"].introspection.table_names()


@pytest.mark.django_db(databases=["log"])
def test_incoming_event_type_outside_choices_refused_by_db() -> None:
    with pytest.raises(IntegrityError, match="incoming_request_response_events_type_valid"):
        create_incoming_event(type="OTHER")


def test_incoming_event_str_shows_type_method_path_and_request_id() -> None:
    event = IncomingRequestResponseEvent(
        type=EventType.REQUEST, method="GET", path="/accounts/login/", request_id="req-1"
    )

    assert str(event) == "REQUEST GET /accounts/login/ (req-1)"


@pytest.mark.django_db(databases=["default", "log"])
def test_outgoing_event_saved_in_log_database_only() -> None:
    event = create_outgoing_event()

    table = OutgoingRequestResponseEvent._meta.db_table
    assert event._state.db == "log"
    assert table in connections["log"].introspection.table_names()
    assert table not in connections["default"].introspection.table_names()


@pytest.mark.django_db(databases=["log"])
def test_outgoing_event_type_outside_choices_refused_by_db() -> None:
    with pytest.raises(IntegrityError, match="outgoing_request_response_events_type_valid"):
        create_outgoing_event(type="OTHER")


@pytest.mark.django_db(databases=["log"])
def test_outgoing_event_partner_outside_choices_refused_by_db() -> None:
    with pytest.raises(IntegrityError, match="outgoing_request_response_events_partner_valid"):
        create_outgoing_event(partner="OTHER")


def test_outgoing_event_str_shows_type_partner_name_and_request_id() -> None:
    event = OutgoingRequestResponseEvent(
        type=EventType.REQUEST, partner=Partner.EMAIL, name="password_reset", request_id="req-1"
    )

    assert str(event) == "REQUEST EMAIL password_reset (req-1)"
