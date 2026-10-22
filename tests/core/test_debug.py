from django.views.debug import get_default_exception_reporter_filter


def test_debug_page_hides_broker_url() -> None:
    reporter_filter = get_default_exception_reporter_filter()

    assert (
        reporter_filter.get_safe_settings()["CELERY_BROKER_URL"]
        == reporter_filter.cleansed_substitute
    )
