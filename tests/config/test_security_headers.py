import pytest
from django.test import Client


@pytest.mark.django_db
@pytest.mark.parametrize("path", ["/accounts/login/", "/api/health/live", "/admin/login/"])
def test_response_has_strict_content_security_policy(client: Client, path: str) -> None:
    response = client.get(path)

    directives = dict(
        part.split(" ", 1) for part in response["Content-Security-Policy"].split("; ")
    )
    assert directives == {
        "default-src": "'self'",
        "img-src": "'self' data:",
        "object-src": "'none'",
        "base-uri": "'none'",
        "form-action": "'self'",
        "frame-ancestors": "'none'",
    }


# These URLs carry a token: no other site may see them in a Referer.
@pytest.mark.django_db
@pytest.mark.parametrize(
    "path",
    [
        "/accounts/verify/uid/token/",
        "/accounts/password-reset/uid/token/",
        "/accounts/invite/uid/token/",
    ],
)
def test_token_page_keeps_referrer_on_this_site(client: Client, path: str) -> None:
    response = client.get(path)

    assert response["Referrer-Policy"] == "same-origin"
