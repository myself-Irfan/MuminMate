from django.contrib.admin.views.decorators import staff_member_required
from django.http import HttpRequest, HttpResponse
from ninja import NinjaAPI
from ninja.security import django_auth

from core.api import router as health_router
from core.exceptions import ProblemError
from core.schemas import ProblemOut

# Every endpoint needs a session unless its router opts out.
api = NinjaAPI(
    title="MuminMate API",
    version="1.0.0",
    urls_namespace="api",
    auth=django_auth,
    docs_decorator=staff_member_required,
)
api.add_router("/health", health_router)


@api.exception_handler(ProblemError)
def render_problem(request: HttpRequest, exc: ProblemError) -> HttpResponse:
    body = ProblemOut(type=exc.type, title=exc.status.phrase, status=exc.status, detail=exc.detail)
    response = api.create_response(request, body.model_dump(), status=exc.status)
    response["Content-Type"] = "application/problem+json"
    return response
