from django.test import RequestFactory

from core.client_ip import get_client_ip


def test_get_client_ip_returns_remote_addr(rf: RequestFactory) -> None:
    request = rf.get("/", REMOTE_ADDR="203.0.113.7")

    assert get_client_ip(request) == "203.0.113.7"


def test_get_client_ip_ignores_forwarded_for_header(rf: RequestFactory) -> None:
    request = rf.get("/", REMOTE_ADDR="203.0.113.7", HTTP_X_FORWARDED_FOR="1.2.3.4")

    assert get_client_ip(request) == "203.0.113.7"


def test_get_client_ip_none_when_unknown(rf: RequestFactory) -> None:
    request = rf.get("/")
    del request.META["REMOTE_ADDR"]

    assert get_client_ip(request) is None
