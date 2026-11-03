import json

from django.conf import settings
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.http import FileResponse, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.views.decorators.http import require_GET, require_http_methods
from django.views.decorators.csrf import ensure_csrf_cookie
from django.contrib.auth import get_user_model

from accounts.roles import get_user_role
from products.models import Product

from .models import IncidentReview, IncidentReviewHistory, Inspection, InspectionBatch, InspectionReview, QualityIncident, QualityIncidentBatch
from .services.quality_incidents import EvidenceError, build_evidence, source_pdf
from .services.validation import validate_image
from .tasks import process_inspection, process_quality_incident_batch
from .services.evaluation import evaluate_samples
from .services.integrity import verify_model_integrity

User = get_user_model()


def _role(request):
    return get_user_role(request.user)


def _engineer(request):
    return request.user.is_authenticated and _role(request) == "Engineer"


def _supervisor(request):
    return request.user.is_authenticated and _role(request) == "Supervisor"


def _inspection_display_label(item):
    if item.predicted_class not in {"Normal", "Defective"}:
        return "Pending"
    prefix = "D" if item.predicted_class == "Defective" else "N"
    earlier = Inspection.objects.filter(
        predicted_class=item.predicted_class,
    ).filter(
        Q(created_at__lt=item.created_at) | Q(created_at=item.created_at, pk__lte=item.pk)
    ).count()
    return f"{prefix}{earlier}"


def _record(item):
    review = getattr(item, "review", None)
    return {
        "id": item.pk,
        "inspection_id": str(item.inspection_id),
        "display_label": _inspection_display_label(item),
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


def _incident_record(incident):
    review = getattr(incident, "review", None)
    inspection_review = getattr(incident.inspection, "review", None)
    history = incident.review_history.all() if hasattr(incident, "review_history") else []
    return {
        "id": incident.pk,
        "incident_id": f"QI-{incident.pk}",
        "inspection_id": str(incident.inspection.inspection_id),
        "inspection_label": _inspection_display_label(incident.inspection),
        "inspection_status": incident.inspection.status,
        "image_url": incident.inspection.image.url if incident.inspection.image else None,
        "original_filename": incident.inspection.original_filename,
        "product_id": incident.product_id,
        "original_prediction": incident.original_prediction,
        "confidence": incident.inspection.confidence,
        "human_correction": {
            "reviewed_class": inspection_review.reviewed_class,
            "reviewer": inspection_review.reviewer.get_username(),
            "comment": inspection_review.comment,
        } if inspection_review else None,
        "model_version": incident.model_version or None,
        "summary": incident.summary,
        "suggested_actions": incident.suggested_actions or [],
        "source_references": incident.source_references or [],
        "evidence_status": incident.evidence_status,
        "evidence_reason": incident.evidence_reason or None,
        "created_by": incident.created_by.get_username(),
        "created_at": incident.created_at.isoformat(),
        "updated_at": incident.updated_at.isoformat(),
        "review_status": incident.review_status,
        "review": {
            "status": review.status,
            "reviewer": review.reviewer.get_username() if review.reviewer_id else None,
            "comment": review.comment,
            "reviewed_at": review.reviewed_at.isoformat() if review.reviewed_at else None,
            "history": [{
                "status": item.status,
                "reviewer": item.reviewer.get_username(),
                "comment": item.comment,
                "reviewed_at": item.reviewed_at.isoformat(),
                "changed_by": item.changed_by.get_username(),
                "changed_at": item.changed_at.isoformat(),
            } for item in history],
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
def quality_incident_inspections(request):
    if not _engineer(request):
        return JsonResponse({"detail": "Engineer role required."}, status=403)
    items = Inspection.objects.filter(submitted_by=request.user).select_related("product").prefetch_related("quality_incident").order_by("-created_at")[:200]
    records = []
    for item in items:
        records.append({
        "display_label": _inspection_display_label(item),
        "inspection_id": str(item.inspection_id),
        "product_id": item.product.product_code,
        "status": item.status,
        "original_prediction": item.predicted_class or None,
        "model_version": item.model_version or None,
        "image_url": item.image.url if item.image else None,
        "original_filename": item.original_filename,
        "eligible": item.status == Inspection.Status.COMPLETED and item.predicted_class == "Defective",
        "has_incident": hasattr(item, "quality_incident"),
        "reason": None if item.status == Inspection.Status.COMPLETED and item.predicted_class == "Defective" else "Only completed inspections with an original Defective prediction can create an incident.",
        })
    return JsonResponse({"inspections": records})


def _incident_batch_record(batch):
    return {
        "batch_id": str(batch.batch_id),
        "status": batch.status,
        "total_items": batch.total_items,
        "completed_items": batch.completed_items,
        "failed_items": batch.failed_items,
        "progress_percent": round(((batch.completed_items + batch.failed_items) / batch.total_items) * 100) if batch.total_items else 100,
        "items": batch.items,
        "error_reason": batch.error_reason or None,
        "created_at": batch.created_at.isoformat(),
        "updated_at": batch.updated_at.isoformat(),
    }


@require_http_methods(["POST"])
def quality_incident_batch_create(request):
    if not _engineer(request):
        return JsonResponse({"detail": "Engineer role required."}, status=403)
    try:
        payload = _json(request)
        inspection_ids = payload.get("inspection_ids")
    except ValueError as exc:
        return JsonResponse({"detail": str(exc)}, status=400)
    if not isinstance(inspection_ids, list):
        return JsonResponse({"detail": "inspection_ids must be a list."}, status=400)
    inspection_ids = list(dict.fromkeys(str(value).strip() for value in inspection_ids if str(value).strip()))
    if not 2 <= len(inspection_ids) <= 10:
        return JsonResponse({"detail": "Select between 2 and 10 inspections for a background batch."}, status=400)
    inspections = list(Inspection.objects.filter(
        inspection_id__in=inspection_ids, submitted_by=request.user
    ).select_related("product"))
    if len(inspections) != len(inspection_ids):
        return JsonResponse({"detail": "One or more inspections were not found or do not belong to you."}, status=404)
    invalid = [str(item.inspection_id) for item in inspections if item.status != Inspection.Status.COMPLETED or item.predicted_class != "Defective"]
    if invalid:
        return JsonResponse({"detail": "Only completed inspections with the original Defective prediction can be queued.", "invalid_inspections": invalid}, status=409)
    simulate = settings.DEBUG and payload.get("simulate_missing_evidence") is True
    with transaction.atomic():
        batch = QualityIncidentBatch.objects.create(
            created_by=request.user,
            total_items=len(inspection_ids),
            items=[{"inspection_id": inspection_id, "status": "queued", "incident_id": None, "error": None, "simulate_missing_evidence": simulate} for inspection_id in inspection_ids],
        )
        transaction.on_commit(lambda: process_quality_incident_batch.delay(batch.pk))
    return JsonResponse(_incident_batch_record(batch), status=202)


@require_GET
def quality_incident_batch_detail(request, batch_id):
    if not _engineer(request) and not _supervisor(request):
        return JsonResponse({"detail": "Engineer or Supervisor role required."}, status=403)
    batch = get_object_or_404(QualityIncidentBatch, batch_id=batch_id)
    if _role(request) == "Engineer" and batch.created_by_id != request.user.id:
        return JsonResponse({"detail": "You can only view your own incident batches."}, status=403)
    return JsonResponse(_incident_batch_record(batch))


@require_http_methods(["GET", "POST"])
def quality_incident_collection(request):
    if not request.user.is_authenticated:
        return JsonResponse({"detail": "Authentication credentials were not provided."}, status=401)
    role = _role(request)
    if role not in {"Engineer", "Supervisor"}:
        return JsonResponse({"detail": "Engineer or Supervisor role required."}, status=403)
    if request.method == "GET":
        queryset = QualityIncident.objects.select_related("inspection", "created_by").prefetch_related("review__reviewer", "review_history__reviewer", "review_history__changed_by", "inspection__review__reviewer")
        if role == "Engineer":
            queryset = queryset.filter(inspection__submitted_by=request.user)
        return JsonResponse({"incidents": [_incident_record(item) for item in queryset[:200]]})
    if role != "Engineer":
        return JsonResponse({"detail": "Only an Engineer can create a quality incident."}, status=403)
    try:
        payload = _json(request)
        inspection_id = payload.get("inspection_id")
    except ValueError as exc:
        return JsonResponse({"detail": str(exc)}, status=400)
    if not inspection_id:
        return JsonResponse({"detail": "inspection_id is required."}, status=400)
    try:
        with transaction.atomic():
            inspection = Inspection.objects.select_for_update().select_related("product").get(
                inspection_id=inspection_id, submitted_by=request.user
            )
            existing = QualityIncident.objects.select_related("inspection", "created_by").prefetch_related("review__reviewer", "review_history__reviewer", "review_history__changed_by", "inspection__review__reviewer").filter(inspection=inspection).first()
            if existing:
                return JsonResponse(_incident_record(existing), status=200)
            if inspection.status != Inspection.Status.COMPLETED or inspection.predicted_class != "Defective":
                return JsonResponse({"detail": "Only a completed inspection with the original Defective prediction can create a quality incident."}, status=409)
            incident = QualityIncident.objects.create(
                inspection=inspection,
                product_id=inspection.product.product_code,
                original_prediction=inspection.predicted_class,
                model_version=inspection.model_version,
                created_by=request.user,
            )
            IncidentReview.objects.create(incident=incident, status=IncidentReview.Status.PENDING)
            try:
                if settings.DEBUG and payload.get("simulate_missing_evidence") is True:
                    raise EvidenceError("Demo mode: a required mapped SOP was marked unavailable for this test.")
                evidence = build_evidence(inspection)
                incident.summary = evidence["summary"]
                incident.suggested_actions = evidence["actions"]
                incident.source_references = evidence["references"]
                incident.evidence_status = QualityIncident.EvidenceStatus.SUFFICIENT
            except Exception as exc:
                incident.evidence_status = QualityIncident.EvidenceStatus.INSUFFICIENT
                incident.evidence_reason = str(exc) or "SOP evidence or incident generation failed."
                incident.summary = f"Inspection {inspection.inspection_id} was flagged by the original model as Defective. Manual review is required because the required SOP evidence is unavailable."
            incident.save()
    except Inspection.DoesNotExist:
        return JsonResponse({"detail": "Inspection not found or it does not belong to you."}, status=404)
    except IntegrityError:
        # The OneToOne database constraint is the final arbiter for two
        # simultaneous requests. Return the winner's unchanged incident.
        existing = QualityIncident.objects.select_related("inspection", "created_by").prefetch_related("review__reviewer", "review_history__reviewer", "review_history__changed_by", "inspection__review__reviewer").filter(
            inspection__inspection_id=inspection_id, inspection__submitted_by=request.user
        ).first()
        if existing:
            return JsonResponse(_incident_record(existing), status=200)
        raise
    return JsonResponse(_incident_record(incident), status=201)


@require_GET
def quality_incident_detail(request, incident_id):
    if not request.user.is_authenticated or _role(request) not in {"Engineer", "Supervisor"}:
        return JsonResponse({"detail": "Engineer or Supervisor role required."}, status=403)
    incident = get_object_or_404(QualityIncident.objects.select_related("inspection", "created_by").prefetch_related("review__reviewer", "review_history__reviewer", "review_history__changed_by", "inspection__review__reviewer"), pk=incident_id)
    if _role(request) == "Engineer" and incident.inspection.submitted_by_id != request.user.id:
        return JsonResponse({"detail": "You can only view your own quality incidents."}, status=403)
    return JsonResponse(_incident_record(incident))


@require_http_methods(["POST", "PATCH"])
def quality_incident_review(request, incident_id):
    if not _supervisor(request):
        return JsonResponse({"detail": "Supervisor role required."}, status=403)
    incident = get_object_or_404(QualityIncident, pk=incident_id)
    try:
        payload = _json(request)
    except ValueError as exc:
        return JsonResponse({"detail": str(exc)}, status=400)
    status = str(payload.get("status", "")).strip()
    comment = str(payload.get("comment", "")).strip()
    allowed = {IncidentReview.Status.APPROVED, IncidentReview.Status.MORE_INFORMATION}
    if status not in allowed:
        return JsonResponse({"detail": "status must be Approved for follow-up or Needs more information."}, status=400)
    if not comment:
        return JsonResponse({"detail": "A review comment is required."}, status=400)
    if status == IncidentReview.Status.APPROVED and incident.evidence_status != QualityIncident.EvidenceStatus.SUFFICIENT:
        return JsonResponse({"detail": "Insufficient-evidence incidents cannot be approved."}, status=409)
    existing_review = IncidentReview.objects.filter(incident=incident).select_related("reviewer").first()
    now = timezone.now()
    if existing_review and existing_review.status != IncidentReview.Status.PENDING and request.method == "POST":
        return JsonResponse({"detail": "This incident already has a saved Supervisor review. Use edit to update it."}, status=409)
    if existing_review:
        if existing_review.status != IncidentReview.Status.PENDING:
            IncidentReviewHistory.objects.create(
                incident=incident,
                status=existing_review.status,
                reviewer=existing_review.reviewer,
                comment=existing_review.comment,
                reviewed_at=existing_review.reviewed_at or now,
                changed_by=request.user,
            )
        existing_review.status = status
        existing_review.reviewer = request.user
        existing_review.comment = comment
        existing_review.reviewed_at = now
        existing_review.save(update_fields=["status", "reviewer", "comment", "reviewed_at"])
    else:
        IncidentReview.objects.create(
            incident=incident,
            status=status,
            reviewer=request.user,
            comment=comment,
            reviewed_at=now,
        )
    incident = QualityIncident.objects.select_related("inspection", "created_by").prefetch_related("review__reviewer", "review_history__reviewer", "review_history__changed_by", "inspection__review__reviewer").get(pk=incident.pk)
    return JsonResponse(_incident_record(incident))


@require_GET
def quality_incident_source(request, document_id):
    if not request.user.is_authenticated or _role(request) not in {"Engineer", "Supervisor"}:
        return JsonResponse({"detail": "Engineer or Supervisor role required."}, status=403)
    try:
        path, row = source_pdf(document_id)
        handle = path.open("rb")
    except (EvidenceError, OSError):
        return JsonResponse({"detail": "Source PDF is unavailable."}, status=404)
    response = FileResponse(handle, content_type="application/pdf")
    response["Content-Disposition"] = f'inline; filename="{row["pdf_filename"].replace(chr(34), "")}"'
    return response


@require_GET
def model_integrity(request):
    if not request.user.is_authenticated:
        return JsonResponse({"detail": "Authentication credentials were not provided."}, status=401)
    if _role(request) not in {"Admin", "Supervisor"} and not request.user.is_superuser:
        return JsonResponse({"detail": "Administrator or Supervisor role required."}, status=403)
    return JsonResponse(verify_model_integrity())


@ensure_csrf_cookie
@require_GET
def quality_incidents_page(request):
    if _role(request) not in {"Engineer", "Supervisor"}:
        return JsonResponse({"detail": "Engineer or Supervisor role required."}, status=403)
    return render(request, "inspections/quality_incidents.html", {"is_supervisor": _supervisor(request), "debug": settings.DEBUG})


@ensure_csrf_cookie
@require_GET
def quality_incident_detail_page(request, incident_id):
    if _role(request) not in {"Engineer", "Supervisor"}:
        return JsonResponse({"detail": "Engineer or Supervisor role required."}, status=403)
    incident = get_object_or_404(
        QualityIncident.objects.select_related("inspection", "created_by")
        .prefetch_related("review__reviewer", "review_history__reviewer", "review_history__changed_by", "inspection__review__reviewer"),
        pk=incident_id,
    )
    if _role(request) == "Engineer" and incident.inspection.submitted_by_id != request.user.id:
        return JsonResponse({"detail": "You can only view your own quality incidents."}, status=403)
    return render(
        request,
        "inspections/quality_incident_detail.html",
        {"incident": incident, "inspection_label": _inspection_display_label(incident.inspection), "is_supervisor": _supervisor(request)},
    )


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


@require_GET
def model_evaluation_page(request):
    if not request.user.is_authenticated or (_role(request) not in {"Admin", "Supervisor"} and not request.user.is_superuser):
        return JsonResponse({"detail": "Administrator or Supervisor role required."}, status=403)
    return render(request, "inspections/model_evaluation.html")
