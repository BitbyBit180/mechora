from django.contrib import admin
from django.db import transaction
from django.http import HttpResponseRedirect
from django.shortcuts import render
from django.urls import path, reverse
from django.contrib import messages
from unfold.admin import ModelAdmin

from .models import Inspection, InspectionBatch, InspectionReview
from .tasks import process_inspection
from .services.validation import validate_image
from products.models import Product


@admin.register(InspectionBatch)
class InspectionBatchAdmin(ModelAdmin):
    list_display = ("batch_id", "submitted_by", "total_items", "created_at")
    search_fields = ("batch_id", "submitted_by__username")
    readonly_fields = ("batch_id", "created_at")


@admin.register(Inspection)
class InspectionAdmin(ModelAdmin):
    list_display = ("inspection_id", "product", "submitted_by", "assigned_to", "predicted_class", "status", "created_at")
    list_filter = ("status", "predicted_class", "product")
    search_fields = ("inspection_id", "original_filename", "submitted_by__username", "assigned_to__username")
    readonly_fields = (
        "inspection_id", "batch", "product", "image", "original_filename", "submitted_by",
        "predicted_class", "confidence", "defect_probability", "model_version", "status",
        "failure_reason", "created_at", "completed_at",
    )

    def get_readonly_fields(self, request, obj=None):
        if obj is None:
            return (
                "inspection_id", "batch", "original_filename", "submitted_by",
                "predicted_class", "confidence", "defect_probability", "model_version",
                "status", "failure_reason", "created_at", "completed_at",
            )
        return self.readonly_fields

    def save_model(self, request, obj, form, change):
        if not change:
            obj.submitted_by = request.user
            obj.original_filename = obj.image.name.rsplit("/", 1)[-1] if obj.image else ""
            obj.status = Inspection.Status.QUEUED
        super().save_model(request, obj, form, change)
        if not change:
            transaction.on_commit(lambda: process_inspection.delay(obj.pk))

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("product", "submitted_by", "assigned_to")

    def get_urls(self):
        custom_urls = [
            path(
                "bulk-upload/",
                self.admin_site.admin_view(self.bulk_upload_view),
                name="inspections_inspection_bulk_upload",
            )
        ]
        return custom_urls + super().get_urls()

    def bulk_upload_view(self, request):
        engineers = request.user.__class__.objects.filter(
            groups__name="Engineer", is_active=True
        ).distinct().order_by("username")
        products = Product.objects.filter(is_active=True).order_by("product_code")
        if request.method == "POST":
            product = products.filter(pk=request.POST.get("product_id")).first()
            engineer = engineers.filter(pk=request.POST.get("assigned_to")).first()
            files = request.FILES.getlist("images")
            errors = []
            if not product:
                errors.append("Select an active product.")
            if not engineer:
                errors.append("Select an active Engineer.")
            if not 1 <= len(files) <= 10:
                errors.append("Select between 1 and 10 images.")
            if errors:
                for error in errors:
                    messages.error(request, error)
            else:
                with transaction.atomic():
                    batch = InspectionBatch.objects.create(
                        submitted_by=request.user, total_items=len(files)
                    )
                    queued = 0
                    failed = 0
                    for uploaded_file in files:
                        failure = validate_image(uploaded_file)
                        item = Inspection.objects.create(
                            batch=batch,
                            product=product,
                            image=uploaded_file,
                            original_filename=uploaded_file.name,
                            submitted_by=request.user,
                            assigned_to=engineer,
                            status=Inspection.Status.FAILED if failure else Inspection.Status.QUEUED,
                            failure_reason=failure or "",
                        )
                        if failure:
                            failed += 1
                        else:
                            queued += 1
                            transaction.on_commit(lambda item_id=item.pk: process_inspection.delay(item_id))
                messages.success(
                    request,
                    f"Bulk inspection created: {queued} queued and {failed} failed validation items assigned to {engineer.username}.",
                )
                return HttpResponseRedirect(reverse("admin:inspections_inspection_changelist"))
        context = {
            **self.admin_site.each_context(request),
            "title": "Bulk Assign Inspections",
            "products": products,
            "engineers": engineers,
        }
        return render(request, "admin/inspections/bulk_upload.html", context)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "assigned_to":
            kwargs["queryset"] = db_field.remote_field.model.objects.filter(
                groups__name="Engineer", is_active=True
            ).distinct().order_by("username")
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


@admin.register(InspectionReview)
class InspectionReviewAdmin(ModelAdmin):
    list_display = ("inspection", "reviewed_class", "review_status", "reviewer", "reviewed_at")
    list_filter = ("review_status",)
    search_fields = ("inspection__inspection_id", "reviewer__username")
    readonly_fields = ("inspection", "reviewed_class", "review_status", "reviewer", "comment", "reviewed_at")
