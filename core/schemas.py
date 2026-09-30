from typing import Literal

from ninja import Schema


class HealthOut(Schema):
    status: Literal["ok"]


class ProblemOut(Schema):
    type: str
    title: str
    status: int
    detail: str
