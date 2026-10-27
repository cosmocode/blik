from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class ReviewsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'reviews'
    # Translators: admin app holding review cycles, reviewer tokens and responses (not product reviews)
    verbose_name = _('Reviews')
