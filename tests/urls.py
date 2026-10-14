from django.contrib.auth.decorators import login_not_required
from django.http import HttpRequest, HttpResponse
from django.urls import path


@login_not_required
def crash(request: HttpRequest) -> HttpResponse:
    raise RuntimeError("crash")


urlpatterns = [path("test/crash", crash)]
