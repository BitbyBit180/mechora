from django.urls import path

from .views import manual_collection, manual_pdf


app_name = "manuals"

urlpatterns = [
    path("", manual_collection, name="manual_collection"),
    path("<int:manual_id>/pdf/", manual_pdf, name="pdf"),
]
