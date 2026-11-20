from smtplib import SMTPAuthenticationError
from unittest.mock import Mock

import pytest
from django.core import mail as django_mail
from django.core.mail import EmailMultiAlternatives
from kombu.exceptions import OperationalError
from pytest_django import Settings

from audit.enums import EventType, Partner
from audit.smtp_client import SmtpClient


@pytest.fixture
def mail() -> EmailMultiAlternatives:
    return EmailMultiAlternatives(subject="Reset", body="Hi", to=["user@example.com"])


def test_send_delivers_mail_and_queues_request_and_response(
    mail: EmailMultiAlternatives, outgoing_audit_publish: Mock, settings: Settings
) -> None:
    settings.EMAIL_HOST = "mail.test"
    settings.EMAIL_PORT = 2525

    SmtpClient().send(mail, name="password_reset", recipient_id=42)

    [sent] = django_mail.outbox
    [request], [response] = (call.args for call in outgoing_audit_publish.call_args_list)
    assert (request["type"], request["partner"], request["name"]) == (
        EventType.REQUEST,
        Partner.EMAIL,
        "password_reset",
    )
    assert (request["method"], request["url"]) == ("SMTP", "smtp://mail.test:2525")
    assert request["additional_info"] == {
        "recipient_id": 42,
        "message_id": sent.extra_headers["Message-ID"],
    }
    assert request["data"]["size"] > 0
    assert (response["type"], response["status"], response["error"]) == (
        EventType.RESPONSE,
        250,
        None,
    )


def test_send_records_smtp_code_and_reraises_when_server_refuses(
    mail: EmailMultiAlternatives, outgoing_audit_publish: Mock
) -> None:
    mail.connection = Mock(send_messages=Mock(side_effect=SMTPAuthenticationError(535, b"no")))

    with pytest.raises(SMTPAuthenticationError):
        SmtpClient().send(mail, name="password_reset", recipient_id=42)

    response = outgoing_audit_publish.call_args_list[-1].args[0]
    assert (response["status"], response["error"]) == (
        535,
        {"error_type": "SMTPAuthenticationError"},
    )


def test_send_records_no_status_when_server_unreachable(
    mail: EmailMultiAlternatives, outgoing_audit_publish: Mock
) -> None:
    mail.connection = Mock(send_messages=Mock(side_effect=ConnectionRefusedError()))

    with pytest.raises(ConnectionRefusedError):
        SmtpClient().send(mail, name="password_reset", recipient_id=42)

    response = outgoing_audit_publish.call_args_list[-1].args[0]
    assert (response["status"], response["error"]) == (
        None,
        {"error_type": "ConnectionRefusedError"},
    )


def test_send_delivers_mail_when_audit_queue_fails(
    mail: EmailMultiAlternatives, outgoing_audit_publish: Mock
) -> None:
    outgoing_audit_publish.side_effect = OperationalError("broker unreachable")

    SmtpClient().send(mail, name="password_reset", recipient_id=42)

    assert len(django_mail.outbox) == 1
