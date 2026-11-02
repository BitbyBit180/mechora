from django.urls import path

from .views import machine_manuals


app_name = "engineer"

urlpatterns = [
    path("machines/<str:machine_id>/manuals/", machine_manuals, name="machine_manuals"),
]
