from django.apps import AppConfig


class GovernanceConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "governance"

    def ready(self):
        # Register signal handlers.
        from . import alert  # noqa: F401
