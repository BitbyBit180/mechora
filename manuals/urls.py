from django.urls import path

from .views import manual_pdf


app_name = "manuals"

urlpatterns = [
    path("<int:manual_id>/pdf/", manual_pdf, name="pdf"),
]
