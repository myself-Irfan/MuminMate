from smtplib import SMTPAuthenticationError, SMTPRecipientsRefused, SMTPServerDisconnected

import pytest

from core.smtp import get_smtp_code


@pytest.mark.parametrize(
    ("error", "smtp_code"),
    [
        (SMTPAuthenticationError(535, b"Bad credentials"), 535),
        (
            SMTPRecipientsRefused(
                {"a@example.com": (450, b"Greylisted"), "b@example.com": (550, b"Unknown")}
            ),
            550,
        ),
        (SMTPServerDisconnected(), None),
        (ConnectionRefusedError(), None),
    ],
    ids=["reply", "highest_recipient_code", "no_reply", "no_connection"],
)
def test_get_smtp_code_reads_the_server_reply(error: OSError, smtp_code: int | None) -> None:
    assert get_smtp_code(error) == smtp_code
