from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class ApiConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "api"
    verbose_name = _("API")

    def ready(self):
        """Import signal handlers when app is ready."""
        import api.signals  # noqa
