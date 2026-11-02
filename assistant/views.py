import json

from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET, require_POST

from .models import Question
from machines.models import Machine
from manuals.models import Manual
from rag.pipeline import RAGCitationError, RAGServiceError, answer_question


@require_GET
def chat_page(request):
    if not request.user.is_authenticated:
        from django.shortcuts import redirect

        return redirect("login")
    return render(request, "assistant/chat.html")


def _role_for_user(user):
    """Read role only from server-side user/profile/group data."""

    role = getattr(user, "role", None)
    if role:
        return str(role)
    try:
        profile = user.profile
    except Exception:
        profile = None
    if profile is not None and getattr(profile, "role", None):
        return str(profile.role)
    role_groups = {"Administrator", "Engineer", "Supervisor"}
    return next(
        (group.name for group in user.groups.all() if group.name in role_groups),
        None,
    )


def _parse_json(request):
    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("Request body must be valid JSON.") from exc
    if not isinstance(payload, dict):
        raise ValueError("Request body must be a JSON object.")
    return payload


@require_POST
def ask(request):
    """POST /api/assistant/ask/"""

    if not request.user.is_authenticated:
        return JsonResponse({"detail": "Authentication credentials were not provided."}, status=401)
    if _role_for_user(request.user) != "Engineer":
        return JsonResponse({"detail": "Engineer role required."}, status=403)
    try:
        payload = _parse_json(request)
        machine_value = payload.get("machine_id")
        question_value = payload.get("question")
        machine_id = machine_value.strip() if isinstance(machine_value, str) else ""
        question = question_value.strip() if isinstance(question_value, str) else ""
        if not machine_id or not question:
            return JsonResponse(
                {"detail": "machine_id and question are required."}, status=400
            )
        machine = Machine.objects.get(machine_id=machine_id)
        if not Manual.objects.filter(
            machine=machine, ingestion_status="completed"
        ).exists():
            return JsonResponse(
                {"detail": "The selected machine has no successfully ingested manuals."},
                status=400,
            )
    except ValueError as exc:
        return JsonResponse({"detail": str(exc)}, status=400)
    except Machine.DoesNotExist:
        return JsonResponse({"detail": "Unknown machine_id."}, status=404)

    try:
        result = answer_question(question=question, machine_id=machine_id)
        status = result["status"]
        answer = result.get("answer", "")
        sources = result.get("sources", [])
        response_status = 200
    except (RAGServiceError, RAGCitationError) as exc:
        # Persist failures distinctly from a genuine lack of evidence.
        status = Question.Status.SYSTEM_ERROR
        answer = "The assistant is temporarily unable to answer this question."
        sources = []
        response_status = 503
        error_detail = str(exc)
    Question.objects.create(
        user=request.user,
        machine=machine,
        question_text=question,
        answer_text=answer,
        status=status,
        citations=sources,
    )
    response = {"status": status, "answer": answer, "sources": sources}
    if response_status != 200:
        response["detail"] = error_detail
    return JsonResponse(response, status=response_status)


@require_GET
def history(request):
    if not request.user.is_authenticated:
        return JsonResponse({"detail": "Authentication credentials were not provided."}, status=401)
    query = request.GET.get("q", "").strip()
    questions = Question.objects.filter(user=request.user).select_related("machine")
    if query:
        questions = questions.filter(question_text__icontains=query)
    records = [
        {
            "id": item.pk,
            "question": item.question_text,
            "answer": item.answer_text,
            "status": item.status,
            "machine_id": item.machine.machine_id,
            "citations": item.citations,
            "created_at": item.created_at.isoformat(),
        }
        for item in questions.order_by("-created_at")[:100]
    ]
    return JsonResponse({"history": records})
