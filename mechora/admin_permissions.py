"""
Permission helpers for Django Unfold sidebar navigation and administration access.
Ensures staff users can only view sections corresponding to their assigned permissions.
"""

def can_view_dashboard(request):
    return bool(request.user and request.user.is_active and request.user.is_staff)


def can_view_machines(request):
    if not (request.user and request.user.is_active and request.user.is_staff):
        return False
    if request.user.is_superuser:
        return True
    return bool(getattr(request.user, "id", None) and request.user.has_perm("machines.view_machine"))


def can_view_manuals(request):
    if not (request.user and request.user.is_active and request.user.is_staff):
        return False
    if request.user.is_superuser:
        return True
    return bool(getattr(request.user, "id", None) and request.user.has_perm("manuals.view_manual"))


def can_view_rag_queries(request):
    if not (request.user and request.user.is_active and request.user.is_staff):
        return False
    if request.user.is_superuser:
        return True
    return bool(getattr(request.user, "id", None) and request.user.has_perm("rag.view_ragquerylog"))


def can_view_rag_chunks(request):
    if not (request.user and request.user.is_active and request.user.is_staff):
        return False
    if request.user.is_superuser:
        return True
    return bool(getattr(request.user, "id", None) and request.user.has_perm("rag.view_ragdocumentchunk"))


def can_view_users(request):
    if not (request.user and request.user.is_active and request.user.is_staff):
        return False
    if request.user.is_superuser:
        return True
    return bool(getattr(request.user, "id", None) and request.user.has_perm("auth.view_user"))


def can_view_groups(request):
    if not (request.user and request.user.is_active and request.user.is_staff):
        return False
    if request.user.is_superuser:
        return True
    return bool(getattr(request.user, "id", None) and request.user.has_perm("auth.view_group"))
