from django.urls import path

from .views import ask, history


app_name = "assistant_api"

urlpatterns = [
    path("ask/", ask, name="ask"),
    path("history/", history, name="history"),
]
