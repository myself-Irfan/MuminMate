from datetime import datetime
from http import HTTPStatus
from unittest.mock import Mock

import pytest
from django.contrib import admin
from django.contrib.admin.models import LogEntry
from django.contrib.auth.models import Permission
from django.test import Client
from django.utils import timezone

from users.admin import UserAdmin
from users.models import User
from users.services.user_service import UserService


@pytest.fixture
def password_payload() -> dict[str, str]:
    return {
        "usable_password": "true",
        "password1": "new-placeholder-password",
        "password2": "new-placeholder-password",
    }


def test_add_form_has_only_email(admin_client: Client) -> None:
    response = admin_client.get("/admin/users/user/add/")

    assert response.status_code == HTTPStatus.OK
    assert set(response.context["adminform"].form.fields) == {"email"}


def test_add_invites_user_without_password(admin_client: Client) -> None:
    response = admin_client.post("/admin/users/user/add/", {"email": "Irfan@Example.com"})

    assert response.status_code == HTTPStatus.FOUND
    user = User.objects.get(email="irfan@example.com")
    assert not user.has_usable_password()
    assert not user.is_staff


def test_add_creates_user_through_user_service(
    admin_client: Client, monkeypatch: pytest.MonkeyPatch
) -> None:
    create = Mock(wraps=UserService().create)
    monkeypatch.setattr("users.admin.UserService.create", create)

    admin_client.post("/admin/users/user/add/", {"email": "Irfan@Example.com"})

    create.assert_called_once_with(email="irfan@example.com", password=None)


def test_add_logs_the_created_user(admin_client: Client) -> None:
    admin_client.post("/admin/users/user/add/", {"email": "irfan@example.com"})

    user = User.objects.get(email="irfan@example.com")
    assert LogEntry.objects.get().object_id == str(user.pk)


def test_add_fails_when_email_taken_in_other_case(
    admin_client: Client, consumer_user: User
) -> None:
    response = admin_client.post("/admin/users/user/add/", {"email": "IRFAN@Example.com"})

    assert response.status_code == HTTPStatus.OK
    assert "email" in response.context["adminform"].form.errors
    assert User.objects.filter(email="irfan@example.com").count() == 1


def test_add_fails_when_email_not_ascii(admin_client: Client) -> None:
    response = admin_client.post("/admin/users/user/add/", {"email": "\u0131rfan@example.com"})

    assert response.status_code == HTTPStatus.OK
    assert response.context["adminform"].form.has_error("email", "email_not_ascii")
    assert not User.objects.filter(email="\u0131rfan@example.com").exists()


def test_add_succeeds_when_staff_with_permission(staff_client: Client) -> None:
    response = staff_client.post("/admin/users/user/add/", {"email": "new@example.com"})

    assert response.status_code == HTTPStatus.FOUND
    assert User.objects.filter(email="new@example.com").exists()


def test_change_form_shows_system_fields_read_only(
    admin_client: Client, consumer_user: User
) -> None:
    response = admin_client.get(f"/admin/users/user/{consumer_user.pk}/change/")

    assert response.status_code == HTTPStatus.OK
    adminform = response.context["adminform"]
    system_fields = {"email_verified_at", "last_login", "date_joined"}
    assert system_fields <= set(adminform.readonly_fields)
    assert not system_fields & set(adminform.form.fields)


def test_change_normalizes_email(admin_client: Client, consumer_user: User) -> None:
    response = admin_client.post(
        f"/admin/users/user/{consumer_user.pk}/change/",
        {"email": "Irfan.New@Example.com", "is_active": "on"},
    )

    assert response.status_code == HTTPStatus.FOUND
    consumer_user.refresh_from_db()
    assert consumer_user.email == "irfan.new@example.com"


def test_change_fails_when_email_taken_in_other_case(
    admin_client: Client, consumer_user: User, password: str
) -> None:
    other = User.objects.create_user(email="other@example.com", password=password)

    response = admin_client.post(
        f"/admin/users/user/{other.pk}/change/",
        {"email": "IRFAN@Example.com", "is_active": "on"},
    )

    assert response.status_code == HTTPStatus.OK
    assert "email" in response.context["adminform"].form.errors
    other.refresh_from_db()
    assert other.email == "other@example.com"


def test_change_grants_staff_when_superuser(admin_client: Client, consumer_user: User) -> None:
    response = admin_client.post(
        f"/admin/users/user/{consumer_user.pk}/change/",
        {"email": "irfan@example.com", "is_active": "on", "is_staff": "on"},
    )

    assert response.status_code == HTTPStatus.FOUND
    consumer_user.refresh_from_db()
    assert consumer_user.is_staff


def test_change_fails_when_superuser_loses_staff(admin_client: Client, password: str) -> None:
    other = User.objects.create_superuser(email="other@example.com", password=password)

    response = admin_client.post(
        f"/admin/users/user/{other.pk}/change/",
        {"email": "other@example.com", "is_active": "on", "is_superuser": "on"},
    )

    assert response.status_code == HTTPStatus.OK
    assert response.context["adminform"].form.non_field_errors() == [
        "A superuser must also be staff."
    ]
    other.refresh_from_db()
    assert other.is_staff


def test_change_form_privilege_fields_read_only_when_staff(
    staff_client: Client, consumer_user: User
) -> None:
    response = staff_client.get(f"/admin/users/user/{consumer_user.pk}/change/")

    assert response.status_code == HTTPStatus.OK
    adminform = response.context["adminform"]
    privilege_fields = {"is_staff", "is_superuser", "groups", "user_permissions"}
    assert privilege_fields <= set(adminform.readonly_fields)
    assert not privilege_fields & set(adminform.form.fields)


def test_change_ignores_privilege_fields_when_staff(
    staff_client: Client, consumer_user: User
) -> None:
    response = staff_client.post(
        f"/admin/users/user/{consumer_user.pk}/change/",
        {"email": "irfan@example.com", "is_active": "on", "is_staff": "on", "is_superuser": "on"},
    )

    assert response.status_code == HTTPStatus.FOUND
    consumer_user.refresh_from_db()
    assert not consumer_user.is_staff
    assert not consumer_user.is_superuser


def test_change_forbidden_when_staff_edits_privileged_user(
    staff_client: Client, privileged_user: User
) -> None:
    email = privileged_user.email

    response = staff_client.post(
        f"/admin/users/user/{privileged_user.pk}/change/",
        {"email": "taken-over@example.com", "is_active": "on"},
    )

    assert response.status_code == HTTPStatus.FORBIDDEN
    privileged_user.refresh_from_db()
    assert privileged_user.email == email


def test_password_change_forbidden_when_staff_edits_privileged_user(
    staff_client: Client, privileged_user: User, password_payload: dict[str, str]
) -> None:
    response = staff_client.post(
        f"/admin/users/user/{privileged_user.pk}/password/", password_payload
    )

    assert response.status_code == HTTPStatus.FORBIDDEN
    privileged_user.refresh_from_db()
    assert not privileged_user.check_password(password_payload["password1"])


def test_delete_forbidden_when_staff_deletes_privileged_user(
    staff_client: Client, staff_user: User, privileged_user: User
) -> None:
    staff_user.user_permissions.add(
        Permission.objects.get(content_type__app_label="users", codename="delete_user")
    )

    response = staff_client.post(f"/admin/users/user/{privileged_user.pk}/delete/", {"post": "yes"})

    assert response.status_code == HTTPStatus.FORBIDDEN
    assert User.objects.filter(pk=privileged_user.pk).exists()


def test_password_change_sets_password(
    admin_client: Client, consumer_user: User, password_payload: dict[str, str]
) -> None:
    response = admin_client.post(
        f"/admin/users/user/{consumer_user.pk}/password/", password_payload
    )

    assert response.status_code == HTTPStatus.FOUND
    consumer_user.refresh_from_db()
    assert consumer_user.check_password(password_payload["password1"])


def test_password_change_fails_when_password_too_short(
    admin_client: Client, consumer_user: User, password: str, short_password: str
) -> None:
    response = admin_client.post(
        f"/admin/users/user/{consumer_user.pk}/password/",
        {"usable_password": "true", "password1": short_password, "password2": short_password},
    )

    assert response.status_code == HTTPStatus.OK
    assert "password2" in response.context["form"].errors
    consumer_user.refresh_from_db()
    assert consumer_user.check_password(password)


def test_changelist_search_matches_email(
    admin_client: Client, consumer_user: User, password: str
) -> None:
    User.objects.create_user(email="other@example.com", password=password)

    response = admin_client.get("/admin/users/user/", {"q": "irfan"})

    assert response.status_code == HTTPStatus.OK
    assert list(response.context["cl"].result_list) == [consumer_user]


def test_changelist_filters_unverified(
    admin_client: Client, consumer_user: User, password: str
) -> None:
    User.objects.create_user(
        email="verified@example.com", password=password, email_verified_at=timezone.now()
    )

    response = admin_client.get("/admin/users/user/", {"email_verified_at__isempty": "1"})

    assert response.status_code == HTTPStatus.OK
    assert consumer_user in response.context["cl"].result_list
    assert not any(user.is_email_verified for user in response.context["cl"].result_list)


@pytest.mark.parametrize(("email_verified_at", "verified"), [(None, False), (timezone.now(), True)])
def test_verified_column_reads_is_email_verified(
    email_verified_at: datetime | None, verified: bool
) -> None:
    user = User(email="irfan@example.com", email_verified_at=email_verified_at)

    assert UserAdmin(User, admin.site).verified(user) is verified


@pytest.mark.django_db
def test_changelist_forbidden_when_staff_without_permission(client: Client, password: str) -> None:
    staff = User.objects.create_user(email="staff@example.com", password=password, is_staff=True)
    client.force_login(staff)

    response = client.get("/admin/users/user/")

    assert response.status_code == HTTPStatus.FORBIDDEN


def test_changelist_redirects_to_login_when_not_staff(client: Client, consumer_user: User) -> None:
    client.force_login(consumer_user)

    response = client.get("/admin/users/user/")

    assert response.status_code == HTTPStatus.FOUND
    assert response["Location"].startswith("/admin/login/")
