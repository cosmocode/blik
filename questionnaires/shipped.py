"""
The questionnaires Blik ships and their translations.

The templates come from the fixtures in questionnaires/fixtures, in English. Their translations live in the gettext
domain "questionnaires": the context is the template key, the message the English text of the fixture.
update_translations extracts the texts into locale/<locale>/LC_MESSAGES/questionnaires.po. add_shipped_translations()
puts the compiled translations into the translation tables of every questionnaire made from a template.
"""

import gettext
import json
from pathlib import Path

from django.conf import settings
from django.utils.translation import to_locale

from .legacy_config import labels_from_config, options_from_config
from .models import Question, Questionnaire
from .placeholders import LEGACY_NAME_PHRASES, NAME_PLACEHOLDER
from .translations import get_checksum, get_parts, get_text_key

DOMAIN = 'questionnaires'

# The language of the fixtures
SOURCE_LANGUAGE = 'en'

# The name of each template by its key; the fixture of a template is <key>_questionnaire.json
TEMPLATE_NAMES = {
    'professional_skills': 'Professional Skills 360 Review',
    'software_engineering': 'Software Engineering 360 Review',
    'manager_360': 'Manager 360 Review',
    'simple': '360 Degree Feedback',
}


class Missing(gettext.NullTranslations):
    """The fallback of a catalog: pgettext() returns None for a text the catalog does not translate."""

    def pgettext(self, context, message):
        return None


def get_template_texts(key):
    """The English texts of a template as its fixture has them, each once, in the order of the fixture."""

    path = Path(__file__).parent / 'fixtures' / f'{key}_questionnaire.json'
    texts = []

    for item in json.loads(path.read_text()):
        fields = item['fields']

        if item['model'] == 'questionnaires.questionnaire':
            texts.extend([fields['name'], fields['description']])
        elif item['model'] == 'questionnaires.questionsection':
            texts.extend([fields['title'], fields['description']])
        elif item['model'] == 'questionnaires.question':
            question = Question(question_type=fields['question_type'], config=fields['config'])
            texts.extend([
                fields['question_text'],
                *labels_from_config(question).values(),
                *[label for label, weight in options_from_config(question)],
            ])

    return list(dict.fromkeys(text for text in texts if text))


def get_catalogs():
    """The compiled translations of the templates, by language."""

    catalogs = {}

    for code, name in settings.LANGUAGES:
        path = Path(settings.LOCALE_PATHS[0]) / to_locale(code) / 'LC_MESSAGES' / f'{DOMAIN}.mo'

        if code != SOURCE_LANGUAGE and path.exists():
            with path.open('rb') as fp:
                catalog = gettext.GNUTranslations(fp)

            catalog.add_fallback(Missing())
            catalogs[code] = catalog

    return catalogs


def add_name_placeholder(question, template_texts):
    """Put {name} in place of "This person" in the question's text, if the template then has that text."""

    text = question.question_text

    for phrase in LEGACY_NAME_PHRASES:
        text = text.replace(phrase, NAME_PLACEHOLDER)

    if text != question.question_text and text in template_texts:
        question.question_text = text
        question.save(update_fields=['question_text'])


def add_translation(part, language, catalog, key):
    """Translate the part's texts that the catalog translates, unless the part has a translation into language."""

    relation = part.translations

    if any(translation.language == language for translation in relation.all()):
        return

    translation = relation.model(**{relation.field.name: part, 'language': language})

    for (field, item), source in part.get_source_texts().items():
        text = catalog.pgettext(key, source)

        if text is None:
            continue

        if item:
            getattr(translation, field)[item] = text
        else:
            setattr(translation, field, text)

        translation.source_checksums[get_text_key(field, item)] = get_checksum(source)

    if translation.source_checksums:
        translation.save()


def add_shipped_translations():
    """
    Give the questionnaires made from a template their template key, put {name} into their question texts and add the
    shipped translations. Texts edited since are left alone, as are parts that have a translation into a language.
    Returns the number of questionnaires made from a template.
    """

    for key, name in TEMPLATE_NAMES.items():
        Questionnaire.objects.filter(name=name, template_key='').update(template_key=key)

    catalogs = get_catalogs()
    template_texts = {key: set(get_template_texts(key)) for key in TEMPLATE_NAMES}
    questionnaires = Questionnaire.objects.filter(template_key__in=TEMPLATE_NAMES, source_language=SOURCE_LANGUAGE)

    for questionnaire in questionnaires:
        key = questionnaire.template_key

        for section, part in get_parts(questionnaire):
            if isinstance(part, Question):
                add_name_placeholder(part, template_texts[key])

            for language, catalog in catalogs.items():
                add_translation(part, language, catalog, key)

    return len(questionnaires)
