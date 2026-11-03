"""
Role definitions and permission management for the MECHORA platform.

Three distinct roles:
1. Admin - Full administration of users, equipment, manuals, and RAG system (non-superuser).
2. Engineer - Authenticated operational staff with access to machines, manuals, and RAG records.
3. Supervisor - Read-only operational oversight across machines, manuals, and question histories.
"""

from django.contrib.auth.models import Group, Permission
from django.db import transaction

ROLE_ADMIN = "Admin"
ROLE_ENGINEER = "Engineer"
ROLE_SUPERVISOR = "Supervisor"

ROLES = [ROLE_ADMIN, ROLE_ENGINEER, ROLE_SUPERVISOR]

ROLE_CHOICES = [
    (ROLE_ADMIN, "Admin"),
    (ROLE_ENGINEER, "Engineer"),
    (ROLE_SUPERVISOR, "Supervisor"),
]

# Permissions granted to each role
ROLE_PERMISSIONS_MAP = {
    ROLE_ADMIN: [
        # User & Group management
        ("auth", "add_user"),
        ("auth", "change_user"),
        ("auth", "delete_user"),
        ("auth", "view_user"),
        ("auth", "view_group"),
        # Equipment & Machines
        ("machines", "add_machine"),
        ("machines", "change_machine"),
        ("machines", "delete_machine"),
        ("machines", "view_machine"),
        # Technical Manuals
        ("manuals", "add_manual"),
        ("manuals", "change_manual"),
        ("manuals", "delete_manual"),
        ("manuals", "view_manual"),
        # RAG System
        ("rag", "add_ragquerylog"),
        ("rag", "change_ragquerylog"),
        ("rag", "delete_ragquerylog"),
        ("rag", "view_ragquerylog"),
        ("rag", "add_ragdocumentchunk"),
        ("rag", "change_ragdocumentchunk"),
        ("rag", "delete_ragdocumentchunk"),
        ("rag", "view_ragdocumentchunk"),
        # Phase 2 products and inspections
        ("products", "add_product"),
        ("products", "change_product"),
        ("products", "delete_product"),
        ("products", "view_product"),
        ("inspections", "view_inspection"),
        ("inspections", "add_inspection"),
        ("inspections", "change_inspection"),
        ("inspections", "view_inspectionbatch"),
        ("inspections", "view_inspectionreview"),
        ("inspections", "view_qualityincident"),
    ],
    ROLE_ENGINEER: [
        # Engineering access: read equipment, documentation, and query logs
        ("machines", "view_machine"),
        ("manuals", "view_manual"),
        ("rag", "view_ragquerylog"),
        ("rag", "view_ragdocumentchunk"),
        ("products", "view_product"),
        ("inspections", "add_inspection"),
        ("inspections", "view_inspection"),
        ("inspections", "view_qualityincident"),
    ],
    ROLE_SUPERVISOR: [
        # Supervisor access: read equipment, documentation, and operational monitoring
        ("machines", "view_machine"),
        ("manuals", "view_manual"),
        ("rag", "view_ragquerylog"),
        ("rag", "view_ragdocumentchunk"),
        ("products", "view_product"),
        ("inspections", "view_inspection"),
        ("inspections", "view_inspectionbatch"),
        ("inspections", "view_inspectionreview"),
        ("inspections", "add_inspectionreview"),
        ("inspections", "change_inspectionreview"),
        ("inspections", "view_qualityincident"),
        ("inspections", "view_incidentreview"),
        ("inspections", "view_incidentreviewhistory"),
        ("inspections", "add_incidentreview"),
        ("inspections", "change_incidentreview"),
        ("inspections", "view_incidentreviewhistory"),
    ],
}


def ensure_roles_and_permissions():
    """
    Creates or reuses the three designated Django Groups and configures their permissions.
    Safe to run repeatedly; ensures idempotent setup.
    """
    created_or_updated = {}

    with transaction.atomic():
        for role_name in ROLES:
            group, _ = Group.objects.get_or_create(name=role_name)
            expected_perms = ROLE_PERMISSIONS_MAP.get(role_name, [])

            perm_objs = []
            for app_label, codename in expected_perms:
                perm = Permission.objects.filter(
                    content_type__app_label=app_label, codename=codename
                ).first()
                if perm:
                    perm_objs.append(perm)

            group.permissions.set(perm_objs)
            created_or_updated[role_name] = group

    return created_or_updated


def get_user_role(user):
    """
    Returns the user's role name ('Superuser', 'Admin', 'Engineer', 'Supervisor', or None).
    """
    if not user or not user.is_authenticated:
        return None
    if user.is_superuser:
        return "Superuser"

    user_group_names = set(user.groups.values_list("name", flat=True))
    for role in ROLES:
        if role in user_group_names:
            return role
    return None


def assign_user_role(user, role_name):
    """
    Enforces that the user belongs to exactly one application role.
    Removes any conflicting role groups and sets is_staff=True.
    """
    ensure_roles_and_permissions()

    # Disassociate from all existing application role groups
    role_groups = Group.objects.filter(name__in=ROLES)
    user.groups.remove(*role_groups)

    if role_name in ROLES:
        target_group = Group.objects.get(name=role_name)
        user.groups.add(target_group)
        user.is_staff = True
        if not user.is_superuser:
            user.is_superuser = False
        user.save(update_fields=["is_staff", "is_superuser"])
