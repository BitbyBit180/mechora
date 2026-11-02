from django.contrib import admin
from unfold.admin import ModelAdmin

from .models import Product


@admin.register(Product)
class ProductAdmin(ModelAdmin):
    list_display = ("product_code", "name", "is_active", "created_at", "updated_at")
    list_filter = ("is_active",)
    search_fields = ("product_code", "name", "description")
    readonly_fields = ("created_at", "updated_at")
