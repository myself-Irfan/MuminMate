import pytest
from django.test import Client

from users.models import User


def test_page_not_stored_when_logged_in(client: Client, consumer_user: User) -> None:
    client.force_login(consumer_user)

    response = client.get("/")

    assert "no-store" in response["Cache-Control"]


@pytest.mark.django_db
def test_page_cache_unchanged_when_anonymous(client: Client) -> None:
    response = client.get("/accounts/signup/")

    assert "no-store" not in response.get("Cache-Control", "")
