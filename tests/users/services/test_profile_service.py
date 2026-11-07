from datetime import date

from users.enums import Gender
from users.models import Profile, User
from users.services.profile_service import ProfileService


def test_get_profile_returns_saved_profile(consumer_user: User) -> None:
    saved = Profile.objects.create(
        user=consumer_user, display_name="Irfan", birth_date=date(1996, 4, 17)
    )

    profile = ProfileService().get_profile(consumer_user)

    assert profile == saved


def test_get_profile_returns_unsaved_profile_when_none_saved(consumer_user: User) -> None:
    profile = ProfileService().get_profile(consumer_user)

    assert profile.pk is None
    assert profile.user == consumer_user
    assert not Profile.objects.exists()


def test_has_profile_false_when_none_saved(consumer_user: User) -> None:
    assert not ProfileService().has_profile(consumer_user)


def test_has_profile_true_when_saved(consumer_user: User) -> None:
    Profile.objects.create(user=consumer_user, display_name="Irfan", birth_date=date(1996, 4, 17))

    assert ProfileService().has_profile(consumer_user)


def test_save_profile_creates_profile_when_none_saved(consumer_user: User) -> None:
    ProfileService().save_profile(
        consumer_user, {"display_name": "Irfan", "birth_date": date(1996, 4, 17)}
    )

    profile = Profile.objects.get(user=consumer_user)
    assert (profile.display_name, profile.birth_date) == ("Irfan", date(1996, 4, 17))


def test_save_profile_changes_only_given_fields(consumer_user: User) -> None:
    Profile.objects.create(user=consumer_user, display_name="Irfan", birth_date=date(1996, 4, 17))

    ProfileService().save_profile(consumer_user, {"gender": Gender.MALE})

    profile = Profile.objects.get(user=consumer_user)
    assert (profile.display_name, profile.gender) == ("Irfan", Gender.MALE)
