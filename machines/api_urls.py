from django.urls import path

from .views import machine_collection


urlpatterns = [
    path("", machine_collection, name="machine_collection"),
]
