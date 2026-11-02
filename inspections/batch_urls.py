from django.urls import path

from .views import batch_detail, batch_items

app_name = "batches"

urlpatterns = [
    path("<uuid:batch_id>/", batch_detail, name="detail"),
    path("<uuid:batch_id>/items/", batch_items, name="items"),
]
