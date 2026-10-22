from django.http import HttpRequest


# uvicorn has already applied FORWARDED_ALLOW_IPS; never read X-Forwarded-For here.
def get_client_ip(request: HttpRequest) -> str | None:
    return request.META.get("REMOTE_ADDR")
