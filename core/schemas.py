from typing import Literal

from ninja import Schema


class HealthOut(Schema):
    status: Literal["ok"]


class ProblemOut(Schema):
    type: str
    title: str
    status: int
    detail: str


class FieldErrorOut(Schema):
    type: str
    loc: list[str | int]
    msg: str


# RFC 9457 extension member: which fields failed, without the submitted input.
class ValidationProblemOut(ProblemOut):
    errors: list[FieldErrorOut]
