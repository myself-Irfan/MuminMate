from django.contrib import admin
from django.contrib.auth import admin as auth_admin
from django.http import HttpRequest
from django.utils.translation import gettext_lazy as _

from users.forms import UserAdminChangeForm, UserAdminCreationForm
from users.models import User


@admin.register(User)
class UserAdmin(auth_admin.UserAdmin[User]):
    form = UserAdminChangeForm
    add_form = UserAdminCreationForm
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        (
            _("Permissions"),
            {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")},
        ),
        (_("Important dates"), {"fields": ("email_verified_at", "last_login", "date_joined")}),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("email", "usable_password", "password1", "password2"),
            },
        ),
    )
    readonly_fields = ("email_verified_at", "last_login", "date_joined")
    list_display = ("email", "is_staff", "is_active", "verified")
    list_filter = (
        *auth_admin.UserAdmin.list_filter,
        ("email_verified_at", admin.EmptyFieldListFilter),
    )
    search_fields = ("email",)
    ordering = ("email",)

    @admin.display(boolean=True, description=_("Verified"), ordering="email_verified_at")
    def verified(self, obj: User) -> bool:
        return obj.is_email_verified

    # Editing users is superuser-equivalent (Django docs): non-superusers manage consumers only.
    def get_readonly_fields(self, request: HttpRequest, obj: User | None = None) -> tuple[str, ...]:
        readonly = tuple(super().get_readonly_fields(request, obj))
        if request.user.is_superuser:
            return readonly
        return (*readonly, "is_staff", "is_superuser", "groups", "user_permissions")

    def has_change_permission(self, request: HttpRequest, obj: User | None = None) -> bool:
        return self._can_manage(request, obj) and super().has_change_permission(request, obj)

    def has_delete_permission(self, request: HttpRequest, obj: User | None = None) -> bool:
        return self._can_manage(request, obj) and super().has_delete_permission(request, obj)

    def _can_manage(self, request: HttpRequest, target: User | None) -> bool:
        if target is None or request.user.is_superuser:
            return True
        return not target.is_privileged
