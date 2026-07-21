from fastapi import status

from backend.exceptions import DomainException


class AuthException(DomainException):
    pass


class UserAlreadyExistsException(AuthException):
    def __init__(self, field: str = "email") -> None:
        super().__init__(message=f"{field} already in use", status_code=status.HTTP_409_CONFLICT)


class InvalidCredentialsException(AuthException):
    def __init__(self) -> None:
        super().__init__(
            message="invalid email or password", status_code=status.HTTP_401_UNAUTHORIZED
        )


class AccountLockedException(AuthException):
    def __init__(self, retry_after_minutes: int = 15) -> None:
        self.retry_after_minutes = retry_after_minutes
        super().__init__(
            message=(
                f"account locked — too many failed attempts, "
                f"retry after {retry_after_minutes} minutes"
            ),
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            headers={"Retry-After": str(retry_after_minutes * 60)},
        )


class InvalidTokenException(AuthException):
    def __init__(self) -> None:
        super().__init__(
            message="invalid or expired token", status_code=status.HTTP_401_UNAUTHORIZED
        )
