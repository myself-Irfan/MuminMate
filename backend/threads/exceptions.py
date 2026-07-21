from fastapi import status

from backend.exceptions import DomainException


class ThreadException(DomainException):
    pass


class ThreadNotFoundException(ThreadException):
    def __init__(self) -> None:
        super().__init__(message="thread not found", status_code=status.HTTP_404_NOT_FOUND)


class ThreadNotOwnedException(ThreadException):
    def __init__(self) -> None:
        super().__init__(
            message="you do not have access to this thread", status_code=status.HTTP_403_FORBIDDEN
        )
