from enum import StrEnum

from django.db import models


class EventType(models.TextChoices):
    REQUEST = "REQUEST"
    RESPONSE = "RESPONSE"


# Set on the request by audit.signals, read when the response row is built.
class RequestAttribute(StrEnum):
    ERROR = "_audit_error"
    LOGGED_OUT_USER_ID = "_audit_logged_out_user_id"
