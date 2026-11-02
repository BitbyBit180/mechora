from django.contrib.admin.models import LogEntry
from django.contrib.auth import get_user_model
from django.urls import reverse_lazy

User = get_user_model()


def dashboard_callback(request, context):
    """
    Supplies real-time database metrics to the Django Unfold Admin index view.
    Calculates live counts for machines, manuals, users, staff administrators, and RAG logs.
    """
    total_machines = 0
    total_manuals = 0
    total_users = 0
    total_admins = 0
    total_queries = 0

    try:
        from machines.models import Machine
        total_machines = Machine.objects.count()
    except Exception:
        pass

    try:
        from manuals.models import Manual
        total_manuals = Manual.objects.count()
    except Exception:
        pass

    try:
        total_users = User.objects.count()
        total_admins = User.objects.filter(is_staff=True).count()
    except Exception:
        pass

    try:
        from rag.models import RAGQueryLog
        total_queries = RAGQueryLog.objects.count()
    except Exception:
        pass

    context.update({
        "kpi_metrics": [
            {
                "title": "Registered Machines",
                "value": total_machines,
                "icon": "precision_manufacturing",
                "link": reverse_lazy("admin:machines_machine_changelist"),
                "description": "Industrial forming and compression equipment",
            },
            {
                "title": "Technical Manuals",
                "value": total_manuals,
                "icon": "menu_book",
                "link": reverse_lazy("admin:manuals_manual_changelist"),
                "description": "Indexed documentation for operations & maintenance",
            },
            {
                "title": "System Users",
                "value": total_users,
                "icon": "group",
                "link": reverse_lazy("admin:auth_user_changelist"),
                "description": "Registered operators, engineers and supervisors",
            },
            {
                "title": "Staff Administrators",
                "value": total_admins,
                "icon": "admin_panel_settings",
                "link": reverse_lazy("admin:auth_user_changelist"),
                "description": "Privileged administration accounts with staff flags",
            },
        ],
        "total_rag_queries": total_queries,
    })

    return context
