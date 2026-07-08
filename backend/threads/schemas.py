from datetime import datetime

from pydantic import BaseModel, field_validator


def _validate_title(v: str) -> str:
    v = v.strip()
    if not v:
        raise ValueError("title cannot be blank")
    if len(v) > 200:
        raise ValueError("title must be at most 200 characters")
    return v


class CreateThreadRequest(BaseModel):
    title: str | None = None

    @field_validator("title")
    @classmethod
    def validate_title(cls, v: str | None) -> str | None:
        return _validate_title(v) if v is not None else v


class RenameThreadRequest(BaseModel):
    title: str

    @field_validator("title")
    @classmethod
    def validate_title(cls, v: str) -> str:
        return _validate_title(v)


class ThreadOut(BaseModel):
    id: int
    title: str
    created_at: datetime
    expires_at: datetime

    model_config = {"from_attributes": True}
