from django.contrib import admin
from unfold.admin import ModelAdmin, TabularInline
from unfold.decorators import display
from unfold.contrib.filters.admin import RangeDateTimeFilter

from manuals.models import Manual
from .models import Machine


class ManualInline(TabularInline):
    model = Manual
    extra = 0
    fields = ("document_id", "document_name", "revision", "ingestion_status")
    readonly_fields = ("document_id", "document_name", "revision", "ingestion_status")
    show_change_link = True
    can_delete = False
    classes = ["collapse"]


@admin.register(Machine)
class MachineAdmin(ModelAdmin):
    list_display = (
        "machine_id",
        "model",
        "machine_name",
        "display_manuals_count",
        "created_at",
    )
    list_filter = (
        "model",
        ("created_at", RangeDateTimeFilter),
    )
    search_fields = (
        "machine_id",
        "model",
        "machine_name",
        "description",
    )
    ordering = ("machine_id",)
    readonly_fields = ("created_at", "updated_at")
    inlines = [ManualInline]
    list_per_page = 20

    fieldsets = (
        (
            "Equipment Identification",
            {
                "fields": (
                    "machine_id",
                    "model",
                    "machine_name",
                ),
                "description": "Primary identifiers and model designation for industrial equipment.",
            },
        ),
        (
            "Specifications & Notes",
            {
                "fields": ("description",),
                "classes": ["tab"],
            },
        ),
        (
            "System Audit Information",
            {
                "fields": ("created_at", "updated_at"),
                "classes": ["collapse"],
            },
        ),
    )

    @display(description="Attached Manuals", label=True)
    def display_manuals_count(self, obj):
        count = obj.manuals.count()
        return f"{count} Manual{'s' if count != 1 else ''}"
