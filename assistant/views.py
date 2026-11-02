import json

from django.db.models import Count, Q
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_GET, require_POST, require_http_methods

from .models import Question
from machines.models import Machine
from manuals.models import Manual
from rag.pipeline import RAGCitationError, RAGServiceError, answer_question


@require_GET
def chat_page(request):
    if not request.user.is_authenticated:
        return redirect("login")
    role = _role_for_user(request.user)
    if role == "Supervisor":
        return redirect("assistant:supervisor_dashboard")
    if role != "Engineer":
        return redirect("admin:index")
    machines = list(
        Machine.objects.filter(manuals__ingestion_status="completed")
        .distinct()
        .order_by("machine_id")
    )
    is_engineer = _role_for_user(request.user) == "Engineer"
    return render(
        request,
        "assistant/chat.html",
        {
            "machines": machines,
            "is_engineer": is_engineer,
        },
    )


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
    if _role_for_user(request.user) != "Engineer":
        return JsonResponse({"detail": "Engineer role required."}, status=403)
    query = request.GET.get("q", "").strip()
    questions = Question.objects.filter(user=request.user).select_related("machine")
    if query:
        questions = questions.filter(
            Q(question_text__icontains=query) | Q(title__icontains=query)
        )
    records = [
        {
            "id": item.pk,
            "title": item.display_title(),
            "question": item.question_text,
            "answer": item.answer_text,
            "status": item.status,
            "machine_id": item.machine.machine_id,
            "citations": item.citations,
            "is_pinned": item.is_pinned,
            "created_at": item.created_at.isoformat(),
        }
        for item in questions.order_by("-is_pinned", "-created_at")[:100]
    ]
    return JsonResponse({"history": records})


def _question_record(item):
    return {
        "id": item.pk,
        "title": item.display_title(),
        "question": item.question_text,
        "answer": item.answer_text,
        "status": item.status,
        "machine_id": item.machine.machine_id,
        "machine_name": item.machine.machine_name,
        "engineer": item.user.get_username(),
        "citations": item.citations,
        "created_at": item.created_at.isoformat(),
    }


@require_GET
def supervisor_dashboard(request):
    if not request.user.is_authenticated:
        return redirect("login")
    if _role_for_user(request.user) != "Supervisor":
        return JsonResponse({"detail": "Supervisor role required."}, status=403)
    questions = Question.objects.select_related("user", "machine").order_by("-created_at")
    return render(
        request,
        "assistant/supervisor_dashboard.html",
        {
            "total_questions": questions.count(),
            "answered_count": questions.filter(status=Question.Status.ANSWERED).count(),
            "insufficient_count": questions.filter(status=Question.Status.INSUFFICIENT).count(),
            "error_count": questions.filter(status=Question.Status.SYSTEM_ERROR).count(),
            "recent_questions": questions[:5],
        },
    )


@require_GET
def supervisor_history(request):
    if not request.user.is_authenticated:
        return redirect("login")
    if _role_for_user(request.user) != "Supervisor":
        return JsonResponse({"detail": "Supervisor role required."}, status=403)
    status = request.GET.get("status", "").strip().upper()
    questions = Question.objects.select_related("user", "machine").order_by("-created_at")
    if status in {choice[0] for choice in Question.Status.choices}:
        questions = questions.filter(status=status)
    return render(
        request,
        "assistant/supervisor_history.html",
        {"questions": questions[:200], "selected_status": status},
    )


@require_GET
def supervisor_question_detail(request, question_id):
    if not request.user.is_authenticated:
        return redirect("login")
    if _role_for_user(request.user) != "Supervisor":
        return JsonResponse({"detail": "Supervisor role required."}, status=403)
    try:
        question = Question.objects.select_related("user", "machine").get(pk=question_id)
    except Question.DoesNotExist:
        return JsonResponse({"detail": "Question not found."}, status=404)
    return render(request, "assistant/supervisor_detail.html", {"question": question})


@require_GET
def history_all(request):
    if not request.user.is_authenticated:
        return JsonResponse({"detail": "Authentication credentials were not provided."}, status=401)
    if _role_for_user(request.user) != "Supervisor":
        return JsonResponse({"detail": "Supervisor role required."}, status=403)
    status = request.GET.get("status", "").strip().upper()
    questions = Question.objects.select_related("user", "machine").order_by("-created_at")
    if status in {choice[0] for choice in Question.Status.choices}:
        questions = questions.filter(status=status)
    return JsonResponse({"history": [_question_record(item) for item in questions[:200]]})


@require_GET
def history_detail(request, question_id):
    if not request.user.is_authenticated:
        return JsonResponse({"detail": "Authentication credentials were not provided."}, status=401)
    try:
        question = Question.objects.select_related("user", "machine").get(pk=question_id)
    except Question.DoesNotExist:
        return JsonResponse({"detail": "Question not found."}, status=404)
    role = _role_for_user(request.user)
    if role == "Engineer" and question.user_id != request.user.id:
        return JsonResponse({"detail": "You can only view your own history."}, status=403)
    if role not in {"Engineer", "Supervisor"}:
        return JsonResponse({"detail": "Engineer or Supervisor role required."}, status=403)
    return JsonResponse(_question_record(question))


@require_POST
def rename_chat(request, question_id):
    if not request.user.is_authenticated:
        return JsonResponse({"detail": "Authentication credentials were not provided."}, status=401)
    if _role_for_user(request.user) != "Engineer":
        return JsonResponse({"detail": "Engineer role required."}, status=403)
    try:
        question = Question.objects.get(pk=question_id, user=request.user)
    except Question.DoesNotExist:
        return JsonResponse({"detail": "Chat not found."}, status=404)
    try:
        payload = _parse_json(request)
        title = str(payload.get("title", "")).strip()
        if not title:
            return JsonResponse({"detail": "Title cannot be empty."}, status=400)
    except ValueError as exc:
        return JsonResponse({"detail": str(exc)}, status=400)

    question.title = title
    question.save(update_fields=["title"])
    return JsonResponse({"id": question.pk, "title": question.display_title(), "status": "success"})


@require_http_methods(["DELETE", "POST"])
def delete_chat(request, question_id):
    if not request.user.is_authenticated:
        return JsonResponse({"detail": "Authentication credentials were not provided."}, status=401)
    if _role_for_user(request.user) != "Engineer":
        return JsonResponse({"detail": "Engineer role required."}, status=403)
    try:
        question = Question.objects.get(pk=question_id, user=request.user)
    except Question.DoesNotExist:
        return JsonResponse({"detail": "Chat not found."}, status=404)

    question.delete()
    return JsonResponse({"id": question_id, "status": "deleted"})


@require_POST
def pin_chat(request, question_id):
    if not request.user.is_authenticated:
        return JsonResponse({"detail": "Authentication credentials were not provided."}, status=401)
    if _role_for_user(request.user) != "Engineer":
        return JsonResponse({"detail": "Engineer role required."}, status=403)
    try:
        question = Question.objects.get(pk=question_id, user=request.user)
    except Question.DoesNotExist:
        return JsonResponse({"detail": "Chat not found."}, status=404)

    question.is_pinned = not question.is_pinned
    question.save(update_fields=["is_pinned"])
    return JsonResponse({"id": question.pk, "is_pinned": question.is_pinned, "status": "success"})
