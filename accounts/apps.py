from django.apps import AppConfig
from django.db.models.signals import post_migrate


def setup_roles_on_post_migrate(sender, **kwargs):
    """Signal receiver to ensure default MECHORA groups and permissions exist."""
    try:
        from accounts.roles import ensure_roles_and_permissions
        ensure_roles_and_permissions()
    except Exception:
        # Ignore during early migrations where auth/contenttypes tables may not be ready
        pass


class AccountsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "accounts"
    verbose_name = "User Accounts & Security"

    def ready(self):
        # Run after every app's migrations so Phase 2 model permissions also
        # exist before the designated groups are synchronized.
        post_migrate.connect(setup_roles_on_post_migrate, dispatch_uid="mechora.ensure_roles")
