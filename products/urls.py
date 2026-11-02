from django.urls import path

from .views import product_collection, product_detail

app_name = "products"

urlpatterns = [
    path("", product_collection, name="collection"),
    path("<int:product_id>/", product_detail, name="detail"),
]
