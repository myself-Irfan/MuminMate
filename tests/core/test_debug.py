import pytest
from django.views.debug import get_default_exception_reporter_filter


@pytest.mark.parametrize("name", ["CELERY_BROKER_URL", "SECRET_KEY"])
def test_debug_page_hides_credential_settings(name: str) -> None:
    reporter_filter = get_default_exception_reporter_filter()

    assert reporter_filter.get_safe_settings()[name] == reporter_filter.cleansed_substitute
