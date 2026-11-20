from smtplib import SMTPRecipientsRefused, SMTPResponseException


# The code only: the reply text usually echoes the address.
def get_smtp_code(error: OSError) -> int | None:
    if isinstance(error, SMTPRecipientsRefused):
        return max((code for code, _ in error.recipients.values()), default=None)
    if isinstance(error, SMTPResponseException):
        return error.smtp_code
    return None
