from django.urls import path

from .views import machine_library, machine_manuals


app_name = "engineer"

urlpatterns = [
    path("", machine_library, name="machine_library"),
    path("machines/<str:machine_id>/manuals/", machine_manuals, name="machine_manuals"),
]
