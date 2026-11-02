import json

from django.db import transaction
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.views.decorators.http import require_GET, require_http_methods
from django.contrib.auth import get_user_model

from accounts.roles import get_user_role
from products.models import Product

from .models import Inspection, InspectionBatch, InspectionReview
from .services.validation import validate_image
from .tasks import process_inspection
from .services.evaluation import evaluate_samples

User = get_user_model()


def _role(request):
    return get_user_role(request.user)


def _engineer(request):
    return request.user.is_authenticated and _role(request) == "Engineer"


def _supervisor(request):
    return request.user.is_authenticated and _role(request) == "Supervisor"


def _record(item):
    review = getattr(item, "review", None)
    return {
        "id": item.pk,
        "inspection_id": str(item.inspection_id),
        "batch_id": str(item.batch.batch_id) if item.batch_id else None,
        "product": {"id": item.product_id, "product_code": item.product.product_code, "name": item.product.name},
        "image_url": item.image.url if item.image else None,
        "original_filename": item.original_filename,
        "submitted_by": item.submitted_by.get_username(),
        "assigned_to": item.assigned_to.get_username() if item.assigned_to_id else None,
        "predicted_class": item.predicted_class or None,
        "confidence": item.confidence,
        "defect_probability": item.defect_probability,
        "model_version": item.model_version or None,
        "status": item.status,
        "review_status": item.review_status,
        "failure_reason": item.failure_reason or None,
        "created_at": item.created_at.isoformat(),
        "completed_at": item.completed_at.isoformat() if item.completed_at else None,
        "review": {
            "reviewed_class": review.reviewed_class,
            "reviewer": review.reviewer.get_username(),
            "comment": review.comment,
            "reviewed_at": review.reviewed_at.isoformat(),
        } if review else None,
    }


def _json(request):
    try:
        value = json.loads(request.body.decode("utf-8") or "{}")
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise ValueError("Request body must be valid JSON.")
    if not isinstance(value, dict):
        raise ValueError("Request body must be a JSON object.")
    return value


def _queue(item):
    transaction.on_commit(lambda: process_inspection.delay(item.pk))


def _create_item(uploaded_file, product, user, batch=None):
    failure = validate_image(uploaded_file)
    item = Inspection.objects.create(
        batch=batch,
        product=product,
        image=uploaded_file,
        original_filename=uploaded_file.name,
        submitted_by=user,
        status=Inspection.Status.FAILED if failure else Inspection.Status.QUEUED,
        failure_reason=failure or "",
        completed_at=timezone.now() if failure else None,
    )
    if not failure:
        _queue(item)
    return item


@require_http_methods(["GET", "POST"])
def inspection_collection(request):
    if not request.user.is_authenticated:
        return JsonResponse({"detail": "Authentication credentials were not provided."}, status=401)
    if request.method == "GET":
        queryset = Inspection.objects.select_related("product", "submitted_by", "batch").prefetch_related("review__reviewer")
        if _role(request) == "Engineer":
            queryset = queryset.filter(Q(submitted_by=request.user) | Q(assigned_to=request.user)).distinct()
        elif _role(request) != "Supervisor":
            return JsonResponse({"detail": "Engineer or Supervisor role required."}, status=403)
        predicted = request.GET.get("predicted_class")
        status = request.GET.get("status")
        review_status = request.GET.get("review_status")
        search = request.GET.get("q", "").strip()
        if predicted in {"Normal", "Defective"}:
            queryset = queryset.filter(predicted_class=predicted)
        if status in {choice.value for choice in Inspection.Status}:
            queryset = queryset.filter(status=status)
        product_id = request.GET.get("product_id")
        if product_id:
            queryset = queryset.filter(product_id=product_id)
        created_from = request.GET.get("created_from")
        created_to = request.GET.get("created_to")
        if created_from:
            queryset = queryset.filter(created_at__date__gte=created_from)
        if created_to:
            queryset = queryset.filter(created_at__date__lte=created_to)
        if search:
            queryset = queryset.filter(inspection_id__icontains=search)
        records = [_record(item) for item in queryset[:200]]
        if review_status:
            records = [item for item in records if item["review_status"] == review_status]
        return JsonResponse({"inspections": records})
    if not _engineer(request):
        return JsonResponse({"detail": "Engineer role required."}, status=403)
    files = request.FILES.getlist("images") or request.FILES.getlist("image")
    if len(files) != 1:
        return JsonResponse({"detail": "Submit exactly one image to this endpoint."}, status=400)
    product = get_object_or_404(Product, pk=request.POST.get("product_id"), is_active=True)
    item = _create_item(files[0], product, request.user)
    return JsonResponse(_record(item), status=201)


@require_http_methods(["POST"])
def inspection_batch(request):
    if not _engineer(request):
        return JsonResponse({"detail": "Engineer role required."}, status=403)
    files = request.FILES.getlist("images")
    if not 1 <= len(files) <= 10:
        return JsonResponse({"detail": "A batch must contain between 1 and 10 images."}, status=400)
    product = get_object_or_404(Product, pk=request.POST.get("product_id"), is_active=True)
    with transaction.atomic():
        batch = InspectionBatch.objects.create(submitted_by=request.user, total_items=len(files))
        items = [_create_item(upload, product, request.user, batch=batch) for upload in files]
    return JsonResponse({"batch_id": str(batch.batch_id), "items": [_record(item) for item in items]}, status=201)


@require_GET
def inspection_detail(request, inspection_id):
    if not request.user.is_authenticated:
        return JsonResponse({"detail": "Authentication credentials were not provided."}, status=401)
    item = get_object_or_404(Inspection.objects.select_related("product", "submitted_by", "batch").prefetch_related("review__reviewer"), inspection_id=inspection_id)
    if _role(request) == "Engineer" and request.user.id not in {item.submitted_by_id, item.assigned_to_id}:
        return JsonResponse({"detail": "You can only view your own inspections."}, status=403)
    if _role(request) not in {"Engineer", "Supervisor"}:
        return JsonResponse({"detail": "Engineer or Supervisor role required."}, status=403)
    return JsonResponse(_record(item))


@require_http_methods(["POST"])
def inspection_assign(request, inspection_id):
    if not request.user.is_authenticated:
        return JsonResponse({"detail": "Authentication credentials were not provided."}, status=401)
    if _role(request) != "Admin" and not request.user.is_superuser:
        return JsonResponse({"detail": "Administrator role required."}, status=403)
    item = get_object_or_404(Inspection, inspection_id=inspection_id)
    try:
        payload = _json(request)
        engineer_id = payload.get("engineer_id")
        engineer = User.objects.get(pk=engineer_id, groups__name="Engineer", is_active=True)
    except (ValueError, User.DoesNotExist, TypeError):
        return JsonResponse({"detail": "A valid active Engineer is required."}, status=400)
    item.assigned_to = engineer
    item.save(update_fields=["assigned_to"])
    return JsonResponse(_record(item))


@require_GET
def inspection_status(request, inspection_id):
    if not request.user.is_authenticated:
        return JsonResponse({"detail": "Authentication credentials were not provided."}, status=401)
    item = get_object_or_404(Inspection, inspection_id=inspection_id)
    if _role(request) == "Engineer" and request.user.id not in {item.submitted_by_id, item.assigned_to_id}:
        return JsonResponse({"detail": "You can only view your own inspections."}, status=403)
    if _role(request) not in {"Engineer", "Supervisor"}:
        return JsonResponse({"detail": "Engineer or Supervisor role required."}, status=403)
    return JsonResponse({"inspection_id": str(item.inspection_id), "status": item.status, "review_status": item.review_status, "failure_reason": item.failure_reason or None})


@require_GET
def batch_detail(request, batch_id):
    if not request.user.is_authenticated:
        return JsonResponse({"detail": "Authentication credentials were not provided."}, status=401)
    batch = get_object_or_404(InspectionBatch.objects.select_related("submitted_by"), batch_id=batch_id)
    if _role(request) == "Engineer" and batch.submitted_by_id != request.user.id:
        return JsonResponse({"detail": "You can only view your own batches."}, status=403)
    if _role(request) not in {"Engineer", "Supervisor"}:
        return JsonResponse({"detail": "Engineer or Supervisor role required."}, status=403)
    items = list(batch.items.select_related("product", "submitted_by").prefetch_related("review__reviewer"))
    return JsonResponse({
        "batch_id": str(batch.batch_id), "total_items": batch.total_items,
        "queued": sum(item.status == Inspection.Status.QUEUED for item in items),
        "processing": sum(item.status == Inspection.Status.PROCESSING for item in items),
        "completed": sum(item.status == Inspection.Status.COMPLETED for item in items),
        "failed": sum(item.status == Inspection.Status.FAILED for item in items),
        "items": [_record(item) for item in items],
    })


@require_GET
def batch_items(request, batch_id):
    response = batch_detail(request, batch_id)
    if response.status_code != 200:
        return response
    payload = json.loads(response.content)
    return JsonResponse({"batch_id": payload["batch_id"], "items": payload["items"]})


@require_http_methods(["GET", "POST"])
def inspection_review(request, inspection_id):
    if not _supervisor(request):
        return JsonResponse({"detail": "Supervisor role required."}, status=403)
    item = get_object_or_404(Inspection.objects.select_related("product", "submitted_by").prefetch_related("review__reviewer"), inspection_id=inspection_id)
    if request.method == "GET":
        if not hasattr(item, "review"):
            return JsonResponse({"detail": "Inspection has not been reviewed."}, status=404)
        return JsonResponse(_record(item)["review"])
    if item.status != Inspection.Status.COMPLETED:
        return JsonResponse({"detail": "Only completed inspections can be reviewed."}, status=409)
    try:
        payload = _json(request)
    except ValueError as exc:
        return JsonResponse({"detail": str(exc)}, status=400)
    reviewed_class = str(payload.get("reviewed_class", "")).strip()
    if reviewed_class not in {"Normal", "Defective"}:
        return JsonResponse({"detail": "reviewed_class must be Normal or Defective."}, status=400)
    review_status = Inspection.ReviewStatus.CONFIRMED if reviewed_class == item.predicted_class else Inspection.ReviewStatus.CORRECTED
    review, _ = InspectionReview.objects.update_or_create(
        inspection=item,
        defaults={"reviewed_class": reviewed_class, "review_status": review_status, "reviewer": request.user, "comment": str(payload.get("comment", "")).strip()},
    )
    return JsonResponse(_record(item), status=201)


@require_GET
def inspection_statistics(request):
    if not request.user.is_authenticated:
        return JsonResponse({"detail": "Authentication credentials were not provided."}, status=401)
    if _role(request) not in {"Engineer", "Supervisor"}:
        return JsonResponse({"detail": "Engineer or Supervisor role required."}, status=403)
    queryset = Inspection.objects.all() if _role(request) == "Supervisor" else Inspection.objects.filter(Q(submitted_by=request.user) | Q(assigned_to=request.user)).distinct()
    return JsonResponse({
        "total": queryset.count(),
        "normal": queryset.filter(predicted_class="Normal").count(),
        "defective": queryset.filter(predicted_class="Defective").count(),
        "queued": queryset.filter(status=Inspection.Status.QUEUED).count(),
        "processing": queryset.filter(status=Inspection.Status.PROCESSING).count(),
        "completed": queryset.filter(status=Inspection.Status.COMPLETED).count(),
        "failed": queryset.filter(status=Inspection.Status.FAILED).count(),
        "pending_review": queryset.filter(status=Inspection.Status.COMPLETED, review__isnull=True).count(),
    })


@require_GET
def inspection_evaluation(request):
    if not request.user.is_authenticated:
        return JsonResponse({"detail": "Authentication credentials were not provided."}, status=401)
    if _role(request) not in {"Admin", "Supervisor"} and not request.user.is_superuser:
        return JsonResponse({"detail": "Administrator or Supervisor role required."}, status=403)
    return JsonResponse(evaluate_samples())


@require_GET
def inspection_dashboard(request):
    if not _engineer(request):
        return JsonResponse({"detail": "Engineer role required."}, status=403)
    return render(request, "inspections/engineer_dashboard.html")


@require_GET
def supervisor_dashboard(request):
    if not _supervisor(request):
        return JsonResponse({"detail": "Supervisor role required."}, status=403)
    return render(request, "inspections/supervisor_dashboard.html")


@require_GET
def supervisor_question_history(request):
    if not _supervisor(request):
        return JsonResponse({"detail": "Supervisor role required."}, status=403)
    return render(request, "inspections/supervisor_question_history.html")
