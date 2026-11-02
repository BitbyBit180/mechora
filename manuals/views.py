import os

from django.http import FileResponse, JsonResponse
from django.views.decorators.http import require_GET

from .models import Manual


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
