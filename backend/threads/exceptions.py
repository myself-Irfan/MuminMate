from fastapi import status


class ThreadException(Exception):
    def __init__(self, message: str, status_code: int = status.HTTP_400_BAD_REQUEST) -> None:
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class ThreadNotFoundException(ThreadException):
    def __init__(self) -> None:
        super().__init__(message="thread not found", status_code=status.HTTP_404_NOT_FOUND)


class ThreadNotOwnedException(ThreadException):
    def __init__(self) -> None:
        super().__init__(
            message="you do not have access to this thread", status_code=status.HTTP_403_FORBIDDEN
        )
