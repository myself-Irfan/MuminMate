from uuid import uuid4

import pytest
from django.test import RequestFactory
from django_htmx.middleware import HtmxDetails

from chats.http import get_open_thread_id


def test_get_open_thread_id_returns_id_of_thread_page(rf: RequestFactory) -> None:
    public_id = uuid4()
    request = rf.get("/", headers={"HX-Current-URL": f"http://testserver/chats/{public_id}/"})

    assert get_open_thread_id(HtmxDetails(request)) == public_id


@pytest.mark.parametrize(
    "headers",
    [{}, {"HX-Current-URL": "http://testserver/"}, {"HX-Current-URL": "http://testserver/nope/"}],
    ids=["no-current-url", "home", "unknown-path"],
)
def test_get_open_thread_id_returns_none_off_a_thread_page(
    rf: RequestFactory, headers: dict[str, str]
) -> None:
    assert get_open_thread_id(HtmxDetails(rf.get("/", headers=headers))) is None
