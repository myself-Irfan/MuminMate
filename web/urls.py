from django.urls import path

from web.views import HomeView

urlpatterns = [
    path("", HomeView.as_view(), name=HomeView.url_name),
]
