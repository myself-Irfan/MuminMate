import pytest
from pytest_django import Settings


# The manifest storage needs `collectstatic`; Django's docs say tests shouldn't use it.
@pytest.fixture(autouse=True)
def plain_static_storage(settings: Settings) -> None:
    settings.STORAGES = {
        **settings.STORAGES,
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    }
