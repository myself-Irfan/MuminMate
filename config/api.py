from http import HTTPStatus

from django.contrib.admin.views.decorators import staff_member_required
from django.http import Http404, HttpRequest, HttpResponse
from ninja import NinjaAPI
from ninja.errors import HttpError, ValidationError
from ninja.security import django_auth

from core.api import router as health_router
from core.exceptions import ProblemError
from core.schemas import FieldErrorOut, ProblemOut, ValidationProblemOut

# Every endpoint needs a session unless its router opts out.
api = NinjaAPI(
    title="MuminMate API",
    version="1.0.0",
    urls_namespace="api",
    auth=django_auth,
    docs_decorator=staff_member_required,
)
api.add_router("/health", health_router)


# RFC 9457 §4.2.1: with type about:blank, the title is the status phrase.
def problem_response(
    request: HttpRequest,
    status: HTTPStatus,
    detail: str,
    *,
    problem_type: str = ProblemError.type,
    errors: list[FieldErrorOut] | None = None,
) -> HttpResponse:
    problem = ProblemOut(type=problem_type, title=status.phrase, status=status, detail=detail)
    if errors is not None:
        problem = ValidationProblemOut(**problem.model_dump(), errors=errors)
    response = api.create_response(request, problem.model_dump(), status=status)
    response["Content-Type"] = "application/problem+json"
    return response


@api.exception_handler(ProblemError)
def render_problem(request: HttpRequest, exc: ProblemError) -> HttpResponse:
    return problem_response(request, exc.status, exc.detail, problem_type=exc.type)


@api.exception_handler(HttpError)
def render_http_error(request: HttpRequest, exc: HttpError) -> HttpResponse:
    return problem_response(request, HTTPStatus(exc.status_code), exc.message)


@api.exception_handler(Http404)
def render_not_found(request: HttpRequest, exc: Http404) -> HttpResponse:
    return problem_response(request, HTTPStatus.NOT_FOUND, "Not found.")


@api.exception_handler(ValidationError)
def render_validation_error(request: HttpRequest, exc: ValidationError) -> HttpResponse:
    errors = [
        FieldErrorOut(type=error["type"], loc=list(error["loc"]), msg=error["msg"])
        for error in exc.errors
    ]
    return problem_response(
        request,
        HTTPStatus.UNPROCESSABLE_CONTENT,
        "The request has invalid fields.",
        errors=errors,
    )
