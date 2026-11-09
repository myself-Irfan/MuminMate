from django.urls import path

from chats.views.chat_views import ChatHomeView, ThreadDetailView
from chats.views.thread_views import (
    ThreadCreateView,
    ThreadDeleteView,
    ThreadListView,
    ThreadRenameView,
    ThreadRowView,
)

urlpatterns = [
    path("", ChatHomeView.as_view(), name=ChatHomeView.url_name),
    path("chats/new/", ThreadCreateView.as_view(), name=ThreadCreateView.url_name),
    path("chats/page/", ThreadListView.as_view(), name=ThreadListView.url_name),
    path("chats/<uuid:public_id>/", ThreadDetailView.as_view(), name=ThreadDetailView.url_name),
    path("chats/<uuid:public_id>/row/", ThreadRowView.as_view(), name=ThreadRowView.url_name),
    path(
        "chats/<uuid:public_id>/rename/", ThreadRenameView.as_view(), name=ThreadRenameView.url_name
    ),
    path(
        "chats/<uuid:public_id>/delete/", ThreadDeleteView.as_view(), name=ThreadDeleteView.url_name
    ),
]
