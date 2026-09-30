from http import HTTPStatus

from django.http import HttpRequest
from ninja import Router

from core.exceptions import ServiceUnavailableError
from core.schemas import HealthOut, ProblemOut
from core.selectors import db_ready

# Polled by container and load-balancer healthchecks: changing these paths breaks them.
router = Router(tags=["health"])


@router.get("/live", response=HealthOut, url_name="health-live")
def live(request: HttpRequest) -> HealthOut:
    return HealthOut(status="ok")


@router.get(
    "/ready",
    response={HTTPStatus.OK: HealthOut, HTTPStatus.SERVICE_UNAVAILABLE: ProblemOut},
    url_name="health-ready",
)
def ready(request: HttpRequest) -> HealthOut:
    if not db_ready():
        raise ServiceUnavailableError("Database unavailable")
    return HealthOut(status="ok")
