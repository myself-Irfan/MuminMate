from django.http import HttpRequest, HttpResponse
from ninja import NinjaAPI

from core.api import router as health_router
from core.exceptions import ProblemError
from core.schemas import ProblemOut

api = NinjaAPI(title="MuminMate API", version="1.0.0", urls_namespace="api")
api.add_router("/health", health_router)


@api.exception_handler(ProblemError)
def problem(request: HttpRequest, exc: ProblemError) -> HttpResponse:
    body = ProblemOut(type=exc.type, title=exc.status.phrase, status=exc.status, detail=exc.detail)
    response = api.create_response(request, body.model_dump(), status=exc.status)
    response["Content-Type"] = "application/problem+json"
    return response
