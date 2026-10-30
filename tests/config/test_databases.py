import pytest
from django.db import connections


@pytest.mark.django_db(databases=["default", "log"])
def test_log_database_is_its_own_database() -> None:
    with connections["log"].cursor() as cursor:
        cursor.execute("SELECT current_database()")
        row = cursor.fetchone()

    assert row == (connections["log"].settings_dict["NAME"],)
    assert row != (connections["default"].settings_dict["NAME"],)
