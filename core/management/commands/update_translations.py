"""
Update the translation catalogues.

Usage:
    python manage.py update_translations

makemessages with the project's defaults: every language in LANGUAGES except the source
language, no locations and no line wrapping, so a run only changes a catalogue where its
messages changed. All makemessages options still apply.
"""

from django.conf import settings
from django.core.management.commands.makemessages import Command as MakeMessagesCommand
from django.utils.translation import to_locale

IGNORE_PATTERNS = [
    'landing/*',
    'templates/landing/*',
    'staticfiles/*',
    'node_modules/*',
]


class Command(MakeMessagesCommand):
    help = 'Update the translation catalogues without locations and line wrapping'

    def handle(self, *args, **options):
        source_language = settings.LANGUAGE_CODE
        translated = [to_locale(code) for code, name in settings.LANGUAGES if code != source_language]

        options['locale'] = options['locale'] or translated
        options['ignore_patterns'] = [*options['ignore_patterns'], *IGNORE_PATTERNS]
        options['no_location'] = True
        options['no_wrap'] = True

        return super().handle(*args, **options)
