import json

from django.db import IntegrityError
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_http_methods

from accounts.roles import ROLE_ENGINEER, get_user_role

from .models import Machine


def _json_body(request):
    try:
        value = json.loads(request.body.decode("utf-8") or "{}")
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise ValueError("Request body must be valid JSON.")
    if not isinstance(value, dict):
        raise ValueError("Request body must be a JSON object.")
    return value


def _machine_record(machine):
    return {
        "machine_id": machine.machine_id,
        "model": machine.model,
        "machine_name": machine.machine_name,
        "description": machine.description,
        "manual_count": machine.manuals.filter(ingestion_status="completed").count(),
    }


@require_http_methods(["GET", "POST"])
def machine_collection(request):
    if not request.user.is_authenticated:
        return JsonResponse({"detail": "Authentication credentials were not provided."}, status=401)
    role = get_user_role(request.user)
    if request.method == "GET":
        machines = Machine.objects.order_by("machine_id")
        if role == ROLE_ENGINEER:
            machines = machines.filter(manuals__ingestion_status="completed").distinct()
        return JsonResponse({"machines": [_machine_record(machine) for machine in machines]})
    if role != "Admin" and not request.user.is_superuser:
        return JsonResponse({"detail": "Administrator role required."}, status=403)
    try:
        payload = _json_body(request)
        machine_id = str(payload.get("machine_id", "")).strip()
        model = str(payload.get("model", payload.get("model_name", ""))).strip()
        machine_name = str(payload.get("machine_name", model)).strip()
        description = str(payload.get("description", "")).strip()
        if not machine_id or not model:
            return JsonResponse({"detail": "machine_id and model are required."}, status=400)
        machine = Machine.objects.create(
            machine_id=machine_id,
            model=model,
            machine_name=machine_name,
            description=description,
        )
    except ValueError as exc:
        return JsonResponse({"detail": str(exc)}, status=400)
    except IntegrityError:
        return JsonResponse({"detail": "A machine with this machine_id already exists."}, status=409)
    return JsonResponse(_machine_record(machine), status=201)


@require_GET
def machine_manuals(request, machine_id):
    """Engineer-only read-only view of manuals belonging to one machine."""

    if not request.user.is_authenticated:
        return redirect("signin")
    if get_user_role(request.user) != ROLE_ENGINEER:
        return HttpResponseForbidden("Engineer role required.")

    machine = get_object_or_404(Machine, machine_id=machine_id)
    manuals = machine.manuals.filter(
        file__isnull=False, ingestion_status="completed"
    ).order_by("-uploaded_at")
    return render(
        request,
        "machines/manuals.html",
        {"machine": machine, "manuals": manuals},
    )

# Create your views here.
