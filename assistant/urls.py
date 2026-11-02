from django.urls import path

from .views import chat_page


app_name = "assistant"

urlpatterns = [
    path("", chat_page, name="chat"),
]
