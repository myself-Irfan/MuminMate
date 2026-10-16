from django.contrib import admin

from users.forms import StaffAuthenticationForm


class MuminMateAdminSite(admin.AdminSite):
    login_form = StaffAuthenticationForm
