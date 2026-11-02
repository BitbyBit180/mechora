from django.urls import path

from .views import (
    ask,
    delete_chat,
    history,
    history_all,
    history_detail,
    pin_chat,
    rename_chat,
)


app_name = "assistant_api"

urlpatterns = [
    path("ask/", ask, name="ask"),
    path("history/", history, name="history"),
    path("history/all/", history_all, name="history_all"),
    path("history/<int:question_id>/", history_detail, name="history_detail"),
    path("history/<int:question_id>/rename/", rename_chat, name="rename_chat"),
    path("history/<int:question_id>/delete/", delete_chat, name="delete_chat"),
    path("history/<int:question_id>/pin/", pin_chat, name="pin_chat"),
]
