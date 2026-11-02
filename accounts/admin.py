from django.contrib import admin
from django.contrib.auth.admin import GroupAdmin as BaseGroupAdmin, UserAdmin as BaseUserAdmin
from django.contrib.auth.models import Group, User
from unfold.admin import ModelAdmin
from unfold.decorators import display

from .forms import MechoraUserChangeForm, MechoraUserCreationForm
from .roles import (
    ROLE_ADMIN,
    ROLE_ENGINEER,
    ROLE_SUPERVISOR,
    assign_user_role,
    get_user_role,
)

# Unregister default User and Group to replace with Unfold styled admins
if admin.site.is_registered(User):
    admin.site.unregister(User)

if admin.site.is_registered(Group):
    admin.site.unregister(Group)


@admin.register(User)
class UserAdmin(BaseUserAdmin, ModelAdmin):
    add_form = MechoraUserCreationForm
    form = MechoraUserChangeForm

    list_display = (
        "username",
        "email",
        "display_full_name",
        "display_role",
        "is_active",
        "is_staff",
        "is_superuser",
    )
    list_filter = (
        "is_active",
        "is_staff",
        "is_superuser",
        "groups",
    )
    search_fields = ("username", "first_name", "last_name", "email")
    ordering = ("username",)

    add_fieldsets = (
        (
            "User Identity & Profile",
            {
                "classes": ["wide"],
                "fields": (
                    "username",
                    "email",
                    "first_name",
                    "last_name",
                ),
                "description": "Enter the user's primary identity and contact details.",
            },
        ),
        (
            "Role & Access Management",
            {
                "classes": ["wide"],
                "fields": (
                    "role",
                    "is_active",
                ),
                "description": "Assign one of the three designated MECHORA platform roles: Admin, Engineer, or Supervisor.",
            },
        ),
        (
            "Security Credentials (Password Authentication)",
            {
                "classes": ["wide", "mechora-password-section"],
                "fields": (
                    "password1",
                    "password2",
                ),
                "description": "Set a secure password. Use the eye icon toggle to reveal or hide password text.",
            },
        ),
    )

    fieldsets = (
        (
            "User Identity",
            {
                "fields": ("username", "password"),
            },
        ),
        (
            "Personal Information",
            {
                "fields": ("first_name", "last_name", "email"),
            },
        ),
        (
            "Role & Operational Access",
            {
                "fields": ("role", "is_active", "is_staff", "is_superuser"),
                "description": "MECHORA platform role assignment. Updating role updates permissions automatically.",
            },
        ),
        (
            "Permission Overrides",
            {
                "classes": ["collapse"],
                "fields": ("groups", "user_permissions"),
            },
        ),
        (
            "Activity Information",
            {
                "classes": ["collapse"],
                "fields": ("last_login", "date_joined"),
            },
        ),
    )

    class Media:
        css = {
            "all": ["accounts/css/user_admin.css"],
        }
        js = ["accounts/js/password_toggle.js"]

    def get_form(self, request, obj=None, **kwargs):
        Form = super().get_form(request, obj, **kwargs)
        if obj is not None and issubclass(Form, MechoraUserChangeForm):
            class FormWithRequestUser(Form):
                def __init__(self, *args, **form_kwargs):
                    form_kwargs["request_user"] = request.user
                    super().__init__(*args, **form_kwargs)

            return FormWithRequestUser
        return Form

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        role = form.cleaned_data.get("role")
        if role and not obj.is_superuser:
            assign_user_role(obj, role)

    def get_fieldsets(self, request, obj=None):
        fieldsets = list(super().get_fieldsets(request, obj))
        if obj and not request.user.is_superuser:
            # Hide superuser flag from non-superusers to prevent privilege escalation
            new_fieldsets = []
            for name, options in fieldsets:
                opts = dict(options)
                if "fields" in opts:
                    fields = list(opts["fields"])
                    if "is_superuser" in fields:
                        fields.remove("is_superuser")
                    opts["fields"] = tuple(fields)
                new_fieldsets.append((name, opts))
            return new_fieldsets
        return fieldsets

    def has_change_permission(self, request, obj=None):
        if not request.user.is_authenticated:
            return False
        if request.user.is_superuser:
            return True
        if obj is not None and obj.is_superuser:
            # Non-superusers cannot modify Superuser accounts
            return False
        return request.user.has_perm("auth.change_user")

    def has_delete_permission(self, request, obj=None):
        if not request.user.is_authenticated:
            return False
        if obj is not None:
            # Prevent deleting self
            if obj == request.user:
                return False
            # Non-superusers cannot delete Superusers
            if obj.is_superuser and not request.user.is_superuser:
                return False
        return request.user.has_perm("auth.delete_user")

    def has_add_permission(self, request):
        if not request.user.is_authenticated:
            return False
        if request.user.is_superuser:
            return True
        return request.user.has_perm("auth.add_user")

    def has_view_permission(self, request, obj=None):
        if not request.user.is_authenticated:
            return False
        if request.user.is_superuser:
            return True
        return request.user.has_perm("auth.view_user")

    @display(description="Full Name")
    def display_full_name(self, obj):
        full = f"{obj.first_name} {obj.last_name}".strip()
        return full if full else "—"

    @display(
        description="Assigned Role",
        label={
            "Superuser": "danger",
            "Admin": "warning",
            "Engineer": "info",
            "Supervisor": "success",
            "Standard User": "secondary",
        },
    )
    def display_role(self, obj):
        if obj.is_superuser:
            return "Superuser"
        role = get_user_role(obj)
        if role:
            return role
        if obj.is_staff:
            return "Staff Admin"
        return "Standard User"


@admin.register(Group)
class GroupAdmin(BaseGroupAdmin, ModelAdmin):
    list_display = ("name", "display_permissions_count")
    search_fields = ("name",)

    @display(description="Assigned Permissions", label=True)
    def display_permissions_count(self, obj):
        count = obj.permissions.count()
        return f"{count} Permission{'s' if count != 1 else ''}"

    def has_delete_permission(self, request, obj=None):
        # Protect default MECHORA roles from accidental deletion
        if obj is not None and obj.name in [ROLE_ADMIN, ROLE_ENGINEER, ROLE_SUPERVISOR]:
            return False
        return super().has_delete_permission(request, obj)
