from pydantic import BaseModel, EmailStr, field_validator


class RegisterRequest(BaseModel):
    email: EmailStr
    username: str
    password: str

    @field_validator("username")
    @classmethod
    def validate_username(cls, username: str) -> str:
        username = username.strip()

        if not (3 <= len(username) <= 50):
            raise ValueError("username must be between 3 and 50 characters")

        return username

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("password must be at least 8 characters")
        return v


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    id: int
    email: str
    username: str

    model_config = {"from_attributes": True}


class RegisterOut(BaseModel):
    message: str
    user: UserOut


class LoginOut(BaseModel):
    message: str
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: UserOut


class TokenOut(BaseModel):
    message: str
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str | None = None


class MessageOut(BaseModel):
    message: str
