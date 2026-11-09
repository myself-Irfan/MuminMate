from datetime import date
from http import HTTPStatus

import pytest
from django.test import Client
from pytest_django.asserts import (
    assertContains,
    assertNotContains,
    assertRedirects,
    assertTemplateUsed,
)

from chats.models import Thread
from users.models import Profile, User


@pytest.mark.django_db
def test_home_requires_login(client: Client) -> None:
    response = client.get("/")

    assertRedirects(response, "/accounts/login/?next=/", fetch_redirect_response=False)


def test_home_renders_chat_home_on_app_layout(consumer_client: Client) -> None:
    response = consumer_client.get("/")

    assert response.status_code == HTTPStatus.OK
    assertTemplateUsed(response, "chats/home.html")
    assertTemplateUsed(response, "app_base.html")
    assertContains(response, "<title>MuminMate</title>", html=True)


def test_home_loads_stylesheets_htmx_and_scripts(consumer_client: Client) -> None:
    response = consumer_client.get("/")

    for path in (
        "/static/vendor/pico/pico.fluid.classless.min.css",
        "/static/css/theme.css",
        "/static/django_htmx/htmx-2.min.js",
        "/static/js/menus.js",
        "/static/js/dialogs.js",
        "/static/js/htmx_errors.js",
    ):
        assertContains(response, path)


def test_home_configures_htmx_without_eval_and_with_422_swap(consumer_client: Client) -> None:
    response = consumer_client.get("/")

    assertContains(response, '"allowEval":false')
    assertContains(response, '"includeIndicatorStyles":false')
    assertContains(response, '{"code":"422","swap":true}')


def test_home_sends_csrf_token_with_htmx_requests(consumer_client: Client) -> None:
    response = consumer_client.get("/")

    token = response.context["csrf_token"]
    assertContains(response, f'hx-headers=\'{{"X-CSRFToken": "{token}"}}\'')


def test_home_greets_by_display_name(consumer_client: Client, consumer_user: User) -> None:
    Profile.objects.create(user=consumer_user, display_name="Irfan", birth_date=date(1996, 4, 17))

    response = consumer_client.get("/")

    assertContains(response, "Assalamu Alaikum, Irfan")


def test_home_greets_without_name_when_no_profile(consumer_client: Client) -> None:
    response = consumer_client.get("/")

    assertContains(response, "Assalamu Alaikum</h1>")


def test_home_invites_first_chat_when_none(consumer_client: Client) -> None:
    response = consumer_client.get("/")

    assertContains(response, "Start your first chat.")
    assertContains(response, '<p class="sidebar-empty">', count=2)
    assertContains(response, "Your chats will appear here.", count=2)


@pytest.mark.usefixtures("thread")
def test_home_offers_new_or_existing_chat_when_some(consumer_client: Client) -> None:
    response = consumer_client.get("/")

    assertContains(response, "Start a new chat, or pick one from your chats.")


def test_home_new_chat_button_posts_to_create(consumer_client: Client) -> None:
    response = consumer_client.get("/")

    assertContains(response, 'action="/chats/new/"')


@pytest.mark.usefixtures("other_thread")
def test_sidebar_lists_own_live_threads_only(consumer_client: Client, thread: Thread) -> None:
    Thread.objects.create(user=thread.user, title="Gone", is_active=False)

    response = consumer_client.get("/")

    assertContains(response, f'href="/chats/{thread.public_id}/"')
    assertNotContains(response, "Not yours")
    assertNotContains(response, "Gone")


def test_sidebar_has_account_menu(consumer_client: Client, consumer_user: User) -> None:
    response = consumer_client.get("/")

    assertContains(response, '<a href="/accounts/profile/">Account</a>', count=2, html=True)
    assertNotContains(response, 'href="/accounts/settings/"')
    assertContains(response, 'action="/accounts/logout/"')
    assertContains(response, consumer_user.email)


@pytest.mark.usefixtures("page_size_two")
def test_sidebar_shows_more_link_when_more_threads_than_page(
    consumer_client: Client, consumer_user: User
) -> None:
    Thread.objects.create(user=consumer_user)
    second = Thread.objects.create(user=consumer_user)
    Thread.objects.create(user=consumer_user)

    response = consumer_client.get("/")

    assertContains(response, f'hx-get="/chats/page/?after={second.public_id}"')
    assertContains(response, f'href="/?after={second.public_id}"')


@pytest.mark.usefixtures("page_size_two")
def test_sidebar_has_no_more_link_when_threads_fit_page(
    consumer_client: Client, consumer_user: User
) -> None:
    Thread.objects.create(user=consumer_user)
    Thread.objects.create(user=consumer_user)

    response = consumer_client.get("/")

    assertNotContains(response, "Show more")


@pytest.mark.usefixtures("page_size_two")
def test_sidebar_after_param_lists_older_threads(
    consumer_client: Client, consumer_user: User
) -> None:
    first = Thread.objects.create(user=consumer_user, title="Oldest")
    second = Thread.objects.create(user=consumer_user, title="Middle")
    Thread.objects.create(user=consumer_user, title="Newest")

    response = consumer_client.get(f"/?after={second.public_id}")

    assertContains(response, f'href="/chats/{first.public_id}/"')
    assertNotContains(response, "Newest")


@pytest.mark.usefixtures("thread")
def test_sidebar_ignores_invalid_after_param(consumer_client: Client) -> None:
    response = consumer_client.get("/?after=nope")

    assertContains(response, "Exam stress")


def test_detail_shows_title_and_empty_note(consumer_client: Client, thread: Thread) -> None:
    response = consumer_client.get(f"/chats/{thread.public_id}/")

    assertTemplateUsed(response, "chats/thread_detail.html")
    assertContains(response, "<h1>Exam stress</h1>", html=True)
    assertContains(response, "No messages yet.")
    assertContains(response, "<title>Exam stress - MuminMate</title>", html=True)


def test_detail_marks_open_thread_in_sidebar(consumer_client: Client, thread: Thread) -> None:
    response = consumer_client.get(f"/chats/{thread.public_id}/")

    assertContains(response, f'href="/chats/{thread.public_id}/" aria-current="page"')


def test_detail_returns_404_for_other_users_thread(
    consumer_client: Client, other_thread: Thread
) -> None:
    response = consumer_client.get(f"/chats/{other_thread.public_id}/")

    assert response.status_code == HTTPStatus.NOT_FOUND


def test_detail_returns_404_for_deleted_thread(consumer_client: Client, thread: Thread) -> None:
    Thread.objects.filter(pk=thread.pk).update(is_active=False)

    response = consumer_client.get(f"/chats/{thread.public_id}/")

    assert response.status_code == HTTPStatus.NOT_FOUND


def test_account_pages_use_app_layout(consumer_client: Client) -> None:
    response = consumer_client.get("/accounts/settings/")

    assertTemplateUsed(response, "app_base.html")
