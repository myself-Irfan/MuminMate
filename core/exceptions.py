from http import HTTPStatus


class ProblemError(Exception):
    status = HTTPStatus.INTERNAL_SERVER_ERROR
    type = "about:blank"

    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.detail = detail


class ServiceUnavailableError(ProblemError):
    status = HTTPStatus.SERVICE_UNAVAILABLE
