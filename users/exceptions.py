from http import HTTPStatus

from core.exceptions import ProblemError


class InvalidVerificationLinkError(ProblemError):
    status = HTTPStatus.BAD_REQUEST


class EmailTakenError(ProblemError):
    status = HTTPStatus.CONFLICT


class InvalidEmailChangeLinkError(ProblemError):
    status = HTTPStatus.BAD_REQUEST


class EmailChangeLinkForOtherAccountError(ProblemError):
    status = HTTPStatus.FORBIDDEN
