"""
Update the translation catalogues.

Usage:
    python manage.py update_translations

makemessages with the project's defaults: the django and djangojs domains unless --domain names
one, every language in LANGUAGES except the source language, no locations and no line wrapping,
so a run only changes a catalogue where its messages changed. All makemessages options still apply.
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

    def add_arguments(self, parser):
        super().add_arguments(parser)
        # Without --domain, every domain is updated.
        parser.set_defaults(domain=None)

    def handle(self, *args, domain, locale, ignore_patterns, **options):
        options['locale'] = self.get_locale(locale)
        options['ignore_patterns'] = [*ignore_patterns, *IGNORE_PATTERNS]
        options['no_location'] = True
        options['no_wrap'] = True

        domains = [domain] if domain else ['django', 'djangojs']

        for domain in domains:
            super().handle(*args, domain=domain, **options)

    @staticmethod
    def get_locale(locale):
        """Returns the given locale or all locales except the source locale."""

        if locale:
            return locale

        source_language = settings.LANGUAGE_CODE

        return [to_locale(code) for code, name in settings.LANGUAGES if code != source_language]
