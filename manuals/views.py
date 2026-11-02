import os

from django.db import IntegrityError, transaction
from django.http import FileResponse, JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_GET, require_POST

from accounts.roles import get_user_role
from machines.models import Machine

from .models import Manual
from .tasks import queue_manual_ingestion


@require_POST
def manual_collection(request):
    if not request.user.is_authenticated:
        return JsonResponse({"detail": "Authentication credentials were not provided."}, status=401)
    if get_user_role(request.user) != "Admin" and not request.user.is_superuser:
        return JsonResponse({"detail": "Administrator role required."}, status=403)
    uploaded_file = request.FILES.get("file")
    machine_id = request.POST.get("machine_id", "").strip()
    document_name = request.POST.get("document_name", "").strip()
    revision = request.POST.get("revision", "1.0").strip() or "1.0"
    document_id = request.POST.get("document_id", "").strip()
    if not uploaded_file or not machine_id or not document_name:
        return JsonResponse(
            {"detail": "file, machine_id, and document_name are required."}, status=400
        )
    machine = get_object_or_404(Machine, machine_id=machine_id)
    if not document_id:
        document_id = f"{machine_id}-{document_name.rsplit('.', 1)[0][:20]}-r{revision}"
    try:
        with transaction.atomic():
            manual = Manual.objects.create(
                document_id=document_id,
                machine=machine,
                document_name=document_name,
                revision=revision,
                pdf_filename=uploaded_file.name,
                file=uploaded_file,
                uploaded_by=request.user,
                ingestion_status=Manual.IngestionStatus.PENDING,
            )
            transaction.on_commit(lambda: queue_manual_ingestion(manual.pk))
    except IntegrityError:
        return JsonResponse(
            {"detail": "A manual with this document ID already exists."}, status=409
        )
    return JsonResponse(
        {
            "id": manual.pk,
            "document_id": manual.document_id,
            "machine_id": machine.machine_id,
            "status": manual.ingestion_status,
        },
        status=201,
    )


@require_GET
def manual_pdf(request, manual_id):
    """Serve a manual inline through an authenticated, access-checked URL."""

    if not request.user.is_authenticated:
        return JsonResponse({"detail": "Authentication credentials were not provided."}, status=401)
    try:
        manual = Manual.objects.get(pk=manual_id)
    except Manual.DoesNotExist:
        return JsonResponse({"detail": "Manual not found."}, status=404)
    if not manual.file:
        return JsonResponse({"detail": "Manual file is unavailable."}, status=404)
    try:
        file_handle = manual.file.open("rb")
    except (FileNotFoundError, OSError):
        return JsonResponse({"detail": "Manual file is unavailable."}, status=404)
    response = FileResponse(file_handle, content_type="application/pdf")
    filename = os.path.basename(manual.document_name or "manual.pdf").replace('"', "")
    response["Content-Disposition"] = f'inline; filename="{filename}"'
    return response

# Create your views here.
