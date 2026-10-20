from django.contrib import admin
from django.contrib.auth import admin as auth_admin
from django.contrib.auth.hashers import UNUSABLE_PASSWORD_PREFIX
from django.db.models import QuerySet
from django.forms import ModelForm
from django.http import HttpRequest
from django.utils.translation import gettext_lazy as _
from django.utils.translation import ngettext

from users.forms.user_admin_forms import UserAdminChangeForm, UserAdminCreationForm
from users.models import User
from users.services.invite_service import InviteService


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
                "fields": ("email",),
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
    actions = ("resend_invite",)

    @admin.display(boolean=True, description=_("Verified"), ordering="email_verified_at")
    def verified(self, obj: User) -> bool:
        return obj.is_email_verified

    def save_model(
        self, request: HttpRequest, obj: User, form: ModelForm[User], change: bool
    ) -> None:
        if change:
            super().save_model(request, obj, form, change)
            return
        created = InviteService().invite(email=obj.email)
        # The admin logs and redirects with obj: give it the new pk.
        obj.pk = created.pk

    @admin.action(description=_("Resend invite"), permissions=["change"])
    def resend_invite(self, request: HttpRequest, queryset: QuerySet[User]) -> None:
        pending = queryset.filter(password__startswith=UNUSABLE_PASSWORD_PREFIX)
        # Non-superusers manage consumers only, as with editing.
        if not request.user.is_superuser:
            pending = pending.filter(is_staff=False, is_superuser=False)
        user_ids = list(pending.values_list("pk", flat=True))
        invites = InviteService()
        for user_id in user_ids:
            invites.resend(user_id)
        self.message_user(
            request,
            ngettext(
                "Invite queued for %(count)d user.",
                "Invite queued for %(count)d users.",
                len(user_ids),
            )
            % {"count": len(user_ids)},
        )

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
