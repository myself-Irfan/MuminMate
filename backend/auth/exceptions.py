class AuthException(Exception):
    def __init__(self, message: str, status_code: int = 400) -> None:
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class UserAlreadyExistsException(AuthException):
    def __init__(self, field: str = "email") -> None:
        super().__init__(f"{field} already in use", status_code=409)


class InvalidCredentialsException(AuthException):
    def __init__(self) -> None:
        super().__init__("invalid email or password", status_code=401)


class AccountLockedException(AuthException):
    def __init__(self, retry_after_minutes: int = 15) -> None:
        self.retry_after_minutes = retry_after_minutes
        super().__init__(
            f"account locked — too many failed attempts, retry after {retry_after_minutes} minutes",
            status_code=429,
        )


class InvalidTokenException(AuthException):
    def __init__(self) -> None:
        super().__init__("invalid or expired token", status_code=401)
