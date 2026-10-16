from django.contrib.admin.apps import AdminConfig


class MuminMateAdminConfig(AdminConfig):
    default_site = "config.admin.MuminMateAdminSite"
