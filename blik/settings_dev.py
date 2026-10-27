"""Local Docker development settings; production continues using settings.py."""
from .settings import *  # noqa: F403


# runserver reloads Python and invalidates template caches when files change.
DEBUG = True
STORAGES = {
    **STORAGES,  # noqa: F405
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}
