"""
Update the translation catalogues.

Usage:
    python manage.py update_translations

makemessages with the project's defaults: the django, djangojs and questionnaires domains unless
--domain names one, every language in LANGUAGES except the source language, no locations, no
obsolete entries and no line wrapping, so a run only changes a catalogue where its messages
changed. All makemessages options still apply.

The questionnaires domain holds the texts of the shipped questionnaires, which come from their
fixtures instead of the code (see questionnaires/shipped.py).
"""

import subprocess
import tempfile
from pathlib import Path

from django.conf import settings
from django.core.management.base import CommandError
from django.core.management.commands.makemessages import Command as MakeMessagesCommand
from django.utils.translation import to_locale

from questionnaires.shipped import DOMAIN as QUESTIONNAIRE_DOMAIN, TEMPLATE_NAMES, get_template_texts

IGNORE_PATTERNS = [
    'landing/*',
    'templates/landing/*',
    'staticfiles/*',
    'node_modules/*',
]

# The options of the gettext tools that match the catalogues makemessages writes
FORMAT_OPTIONS = ['--no-wrap', '--no-location']


def run(*args, source=None):
    """Run a gettext tool with source as its input; returns its output and fails with its errors."""

    result = subprocess.run(args, input=source, capture_output=True, text=True)

    if result.returncode:
        raise CommandError(result.stderr)

    return result.stdout


def get_template_catalogue():
    """
    The PO template of the questionnaires domain. xgettext extracts it from a pgettext() call per text, as makemessages
    extracts the messages of a template from the Python code it turns the template into.
    """

    source = '\n'.join(
        f'pgettext({key!r}, {text!r})' for key in TEMPLATE_NAMES for text in get_template_texts(key)
    )
    catalogue = run(
        'xgettext',
        '--language=Python',
        '--keyword=pgettext:1c,2',
        '--from-code=UTF-8',
        *FORMAT_OPTIONS,
        '--output=-',
        '-',
        source=source,
    )

    # xgettext leaves the charset to be filled in, makemessages fills it in the same way
    return catalogue.replace('charset=CHARSET', 'charset=UTF-8')


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
        options['no_obsolete'] = True
        options['no_wrap'] = True

        domains = [domain] if domain else ['django', 'djangojs', QUESTIONNAIRE_DOMAIN]

        for domain in domains:
            if domain == QUESTIONNAIRE_DOMAIN:
                self.update_questionnaire_catalogues(options['locale'])
            else:
                super().handle(*args, domain=domain, **options)

    @staticmethod
    def get_locale(locale):
        """Returns the given locale or all locales except the source locale."""

        if locale:
            return locale

        source_language = settings.LANGUAGE_CODE

        return [to_locale(code) for code, name in settings.LANGUAGES if code != source_language]

    @staticmethod
    def update_questionnaire_catalogues(locales):
        """Merge the texts of the shipped questionnaires into the questionnaires catalogue of every locale."""

        locale_dir = Path(settings.LOCALE_PATHS[0])

        with tempfile.TemporaryDirectory() as directory:
            template = Path(directory) / f'{QUESTIONNAIRE_DOMAIN}.pot'
            template.write_text(get_template_catalogue(), encoding='utf-8')

            for locale in locales:
                catalogue = locale_dir / locale / 'LC_MESSAGES' / f'{QUESTIONNAIRE_DOMAIN}.po'

                if catalogue.exists():
                    run('msgmerge', *MakeMessagesCommand.msgmerge_options, *FORMAT_OPTIONS, catalogue, template)
                else:
                    catalogue.parent.mkdir(parents=True, exist_ok=True)
                    run('msginit', '--no-translator', '--no-wrap', '--locale', locale, '-i', template, '-o', catalogue)

                run('msgattrib', *MakeMessagesCommand.msgattrib_options, *FORMAT_OPTIONS, '-o', catalogue, catalogue)
