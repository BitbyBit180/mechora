from django.contrib.auth import login, logout
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods

from .forms import PublicSignupForm, RoleAuthenticationForm
from .models import UserProfile
from .roles import ROLE_ADMIN, assign_user_role, get_user_role


def _role_redirect(user):
    role = get_user_role(user)
    if user.is_superuser or role == ROLE_ADMIN:
        return redirect("admin:index")
    if role == "Supervisor":
        return redirect("assistant:supervisor_dashboard")
    return redirect("assistant:chat")

@require_http_methods(["GET", "POST"])
def login_view(request):
    if request.user.is_authenticated:
        return _role_redirect(request.user)
    form = RoleAuthenticationForm(request, data=request.POST or None)
    if request.method == "POST" and form.is_valid():
        login(request, form.get_user())
        return _role_redirect(form.get_user())
    return render(request, "accounts/signin.html", {"form": form})


@require_http_methods(["GET", "POST"])
def signup_view(request):
    if request.user.is_authenticated:
        return _role_redirect(request.user)
    form = PublicSignupForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        role = form.cleaned_data["role"]
        assign_user_role(user, role)
        UserProfile.objects.create(
            user=user,
            role=UserProfile.Role.ENGINEER
            if role == "Engineer"
            else UserProfile.Role.SUPERVISOR,
        )
        login(request, user)
        return redirect("assistant:chat")
    return render(request, "accounts/signup.html", {"form": form})


def logout_view(request):
    logout(request)
    return redirect("login")


@require_http_methods(["POST"])
def login_api(request):
    data = request.POST
    if not data and request.body:
        try:
            data = json.loads(request.body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            data = {}
    form = RoleAuthenticationForm(request, data=data)
    if not form.is_valid():
        return JsonResponse({"detail": "Invalid credentials or role.", "errors": form.errors}, status=401)
    user = form.get_user()
    login(request, user)
    role = get_user_role(user)
    return JsonResponse({"status": "authenticated", "role": "Admin" if role == "Superuser" else role})

# Create your views here.
