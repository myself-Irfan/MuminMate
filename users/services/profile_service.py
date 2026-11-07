from collections.abc import Mapping

from users.models import Profile, User


class ProfileService:
    def get_profile(self, user: User) -> Profile:
        try:
            return Profile.objects.get(user=user)
        except Profile.DoesNotExist:
            return Profile(user=user)

    def has_profile(self, user: User) -> bool:
        return Profile.objects.filter(user=user).exists()

    def save_profile(self, user: User, values: Mapping[str, object]) -> None:
        Profile.objects.update_or_create(user=user, defaults=values)
