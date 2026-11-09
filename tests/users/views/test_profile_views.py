from datetime import date
from http import HTTPStatus

import pytest
from django.test import Client
from pytest_django.asserts import assertContains, assertNotContains, assertTemplateUsed

from users.enums import Gender
from users.models import Profile, User


@pytest.fixture
def profile_payload() -> dict[str, str]:
    return {"display_name": "Irfan", "birth_date": "1996-04-17", "gender": "male"}


@pytest.fixture
def profile(consumer_user: User) -> Profile:
    return Profile.objects.create(
        user=consumer_user, display_name="Irfan", birth_date=date(1996, 4, 17)
    )


def test_welcome_page_shows_profile_form(consumer_client: Client) -> None:
    response = consumer_client.get("/accounts/welcome/")

    assert response.status_code == HTTPStatus.OK
    assertTemplateUsed(response, "users/welcome.html")
    assertContains(response, 'name="display_name"')


def test_welcome_saves_profile_and_redirects_home(
    consumer_client: Client, consumer_user: User, profile_payload: dict[str, str]
) -> None:
    response = consumer_client.post("/accounts/welcome/", profile_payload)

    assert response.status_code == HTTPStatus.FOUND
    assert response["Location"] == "/"
    profile = Profile.objects.get(user=consumer_user)
    assert (profile.display_name, profile.birth_date) == ("Irfan", date(1996, 4, 17))


def test_welcome_redirects_to_next_after_saving(
    consumer_client: Client, profile_payload: dict[str, str]
) -> None:
    response = consumer_client.post("/accounts/welcome/?next=/accounts/profile/", profile_payload)

    assert response["Location"] == "/accounts/profile/"


def test_welcome_ignores_next_on_another_site(
    consumer_client: Client, profile_payload: dict[str, str]
) -> None:
    response = consumer_client.post(
        "/accounts/welcome/?next=https://evil.example/", profile_payload
    )

    assert response["Location"] == "/"


def test_welcome_shows_errors_and_saves_nothing_when_invalid(
    consumer_client: Client, profile_payload: dict[str, str]
) -> None:
    response = consumer_client.post("/accounts/welcome/", {**profile_payload, "display_name": ""})

    assert response.status_code == HTTPStatus.OK
    assertContains(response, "This field is required.")
    assert not Profile.objects.exists()


def test_welcome_skip_link_goes_to_next(consumer_client: Client) -> None:
    response = consumer_client.get("/accounts/welcome/?next=/accounts/profile/")

    assertContains(response, '<a href="/accounts/profile/">Skip</a>', html=True)


def test_welcome_skip_link_goes_home_when_next_on_another_site(consumer_client: Client) -> None:
    response = consumer_client.get("/accounts/welcome/?next=https://evil.example/")

    assertContains(response, '<a href="/">Skip</a>', html=True)


@pytest.mark.usefixtures("profile")
def test_welcome_sends_user_with_profile_to_profile_page(consumer_client: Client) -> None:
    response = consumer_client.get("/accounts/welcome/")

    assert response["Location"] == "/accounts/profile/"


def test_welcome_post_keeps_saved_profile(
    consumer_client: Client, profile: Profile, profile_payload: dict[str, str]
) -> None:
    response = consumer_client.post(
        "/accounts/welcome/", {**profile_payload, "display_name": "Someone else"}
    )

    assert response["Location"] == "/accounts/profile/"
    profile.refresh_from_db()
    assert profile.display_name == "Irfan"


@pytest.mark.django_db
def test_welcome_redirects_to_login_when_anonymous(client: Client) -> None:
    response = client.get("/accounts/welcome/")

    assert response["Location"] == "/accounts/login/?next=/accounts/welcome/"


def test_welcome_redirects_privileged_user_to_admin(client: Client, staff_user: User) -> None:
    client.force_login(staff_user)

    response = client.get("/accounts/welcome/")

    assert response["Location"] == "/admin/"


def test_profile_page_shows_full_form_when_no_profile(consumer_client: Client) -> None:
    response = consumer_client.get("/accounts/profile/")

    assert response.status_code == HTTPStatus.OK
    assertTemplateUsed(response, "users/profile.html")
    assertContains(response, "Save and continue")


def test_profile_page_saves_full_form_when_no_profile(
    consumer_client: Client, consumer_user: User, profile_payload: dict[str, str]
) -> None:
    response = consumer_client.post("/accounts/profile/", profile_payload, follow=True)

    assert response.redirect_chain == [("/accounts/profile/", HTTPStatus.FOUND)]
    assertContains(response, "Your profile is saved.")
    assert Profile.objects.get(user=consumer_user).display_name == "Irfan"


def test_profile_page_shows_full_form_errors_when_no_profile(
    consumer_client: Client, profile_payload: dict[str, str]
) -> None:
    response = consumer_client.post("/accounts/profile/", {**profile_payload, "display_name": ""})

    assert response.status_code == HTTPStatus.OK
    assertContains(response, "This field is required.")
    assertContains(response, "Save and continue")
    assert not Profile.objects.exists()


@pytest.mark.usefixtures("profile")
def test_profile_page_shows_saved_values_as_rows(consumer_client: Client) -> None:
    response = consumer_client.get("/accounts/profile/")

    assertContains(response, "Irfan")
    assertContains(response, "17 April 1996")
    assertContains(response, "Prefer not to say")
    assertNotContains(response, "Save and continue")


def test_profile_row_saves_only_its_field(consumer_client: Client, profile: Profile) -> None:
    response = consumer_client.post(
        "/accounts/profile/", {"row": "gender", "gender": "female"}, follow=True
    )

    assert response.redirect_chain == [("/accounts/profile/", HTTPStatus.FOUND)]
    assertContains(response, "Your profile is saved.")
    profile.refresh_from_db()
    assert (profile.display_name, profile.gender) == ("Irfan", Gender.FEMALE)


def test_profile_row_shows_error_with_row_open(consumer_client: Client, profile: Profile) -> None:
    response = consumer_client.post(
        "/accounts/profile/", {"row": "display_name", "display_name": ""}
    )

    assert response.status_code == HTTPStatus.OK
    assertContains(response, "This field is required.")
    assert response.context["open_row"] == "display_name"
    profile.refresh_from_db()
    assert profile.display_name == "Irfan"


@pytest.mark.usefixtures("profile")
def test_profile_row_refused_when_row_unknown(consumer_client: Client) -> None:
    response = consumer_client.post("/accounts/profile/", {"row": "user", "user": "2"})

    assert response.status_code == HTTPStatus.BAD_REQUEST


@pytest.mark.django_db
def test_profile_page_redirects_to_login_when_anonymous(client: Client) -> None:
    response = client.get("/accounts/profile/")

    assert response["Location"] == "/accounts/login/?next=/accounts/profile/"


def test_profile_page_redirects_privileged_user_to_admin(client: Client, staff_user: User) -> None:
    client.force_login(staff_user)

    response = client.get("/accounts/profile/")

    assert response["Location"] == "/admin/"


@pytest.mark.usefixtures("profile")
def test_account_menu_shows_display_name_then_email(consumer_client: Client) -> None:
    response = consumer_client.get("/")

    assertContains(response, '<span title="Irfan">Irfan</span>', html=True)
    assertContains(
        response, '<span class="sub" title="irfan@example.com">irfan@example.com</span>', html=True
    )


def test_account_menu_shows_email_once_when_no_profile(consumer_client: Client) -> None:
    response = consumer_client.get("/")

    assertContains(
        response, '<span title="irfan@example.com">irfan@example.com</span>', html=True, count=2
    )
    assertNotContains(response, 'class="sub"')


def test_welcome_header_links_email_to_profile(consumer_client: Client) -> None:
    response = consumer_client.get("/accounts/welcome/")

    assertContains(
        response,
        '<a class="account-link" href="/accounts/profile/" title="irfan@example.com">'
        "irfan@example.com</a>",
        html=True,
    )


@pytest.mark.django_db
def test_header_has_no_profile_link_when_logged_out(client: Client) -> None:
    response = client.get("/accounts/login/")

    assertNotContains(response, 'href="/accounts/profile/"')
