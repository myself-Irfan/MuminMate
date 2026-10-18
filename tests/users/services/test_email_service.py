from pathlib import Path
from smtplib import SMTPRecipientsRefused
from unittest.mock import Mock

import pytest
from django.core import mail
from django.core.mail import EmailMultiAlternatives
from django.template import TemplateDoesNotExist
from pytest_django import Settings

from users.models import User
from users.services.email_service import EmailService


@pytest.fixture
def mail_templates(settings: Settings, tmp_path: Path) -> None:
    (tmp_path / "test_emails").mkdir()
    (tmp_path / "test_emails" / "hello.txt").write_text("Hello {{ name }}")
    (tmp_path / "test_emails" / "hello.html").write_text("<p>Hello {{ name }}</p>")
    engine = settings.TEMPLATES[0]
    settings.TEMPLATES = [{**engine, "DIRS": [tmp_path, *engine["DIRS"]]}]


@pytest.mark.usefixtures("mail_templates")
def test_send_mails_user_text_and_html(settings: Settings, consumer_user: User) -> None:
    settings.DEFAULT_FROM_EMAIL = "MuminMate <no-reply@example.com>"

    EmailService().send(
        user=consumer_user,
        subject="Greetings",
        template_name="test_emails/hello",
        context={"name": "Ali"},
    )

    [sent] = mail.outbox
    assert isinstance(sent, EmailMultiAlternatives)
    assert sent.to == [consumer_user.email]
    assert sent.from_email == "MuminMate <no-reply@example.com>"
    assert sent.subject == "Greetings"
    assert sent.body == "Hello Ali"
    assert sent.alternatives == [("<p>Hello Ali</p>", "text/html")]


@pytest.mark.usefixtures("mail_templates")
@pytest.mark.parametrize(
    "error",
    [
        SMTPRecipientsRefused({"user@example.com": (550, b"No such user")}),
        ConnectionRefusedError(),
        TimeoutError(),
    ],
    ids=["refused", "server_down", "timeout"],
)
def test_send_raises_when_mail_server_fails(
    monkeypatch: pytest.MonkeyPatch, consumer_user: User, error: OSError
) -> None:
    monkeypatch.setattr(EmailMultiAlternatives, "send", Mock(side_effect=error))

    with pytest.raises(type(error)):
        EmailService().send(
            user=consumer_user,
            subject="Greetings",
            template_name="test_emails/hello",
            context={"name": "Ali"},
        )


@pytest.mark.usefixtures("mail_templates")
def test_send_raises_when_template_missing(consumer_user: User) -> None:
    with pytest.raises(TemplateDoesNotExist):
        EmailService().send(
            user=consumer_user,
            subject="Greetings",
            template_name="test_emails/missing",
            context={},
        )
