import pytest
from django.utils import timezone
from pytest_django import Settings

from chats.models import Thread
from users.models import User


@pytest.fixture
def other_consumer_user(db: None, password: str) -> User:
    return User.objects.create_user(
        email="other@example.com", password=password, email_verified_at=timezone.now()
    )


@pytest.fixture
def thread(consumer_user: User) -> Thread:
    return Thread.objects.create(user=consumer_user, title="Exam stress")


@pytest.fixture
def other_thread(other_consumer_user: User) -> Thread:
    return Thread.objects.create(user=other_consumer_user, title="Not yours")


@pytest.fixture
def page_size_two(settings: Settings) -> None:
    settings.THREAD_LIST_PAGE_SIZE = 2
