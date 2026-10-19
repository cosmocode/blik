from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class AccountsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'accounts'
    verbose_name = _('Accounts')

    def ready(self):
        import accounts.signals  # noqa
        # Note: Permission groups are auto-initialized on first use via ensure_permission_groups()
        # and created during migration 0005_assign_organization_permissions
