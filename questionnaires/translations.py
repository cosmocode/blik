"""
Translations of questionnaires.

The text fields of a questionnaire, its sections, questions and answer options hold the questionnaire's source language.
Their translations live in one table per model, with one row per language. A text left empty there is not translated,
and the source text is shown instead.
"""

import copy

from django.db.models import prefetch_related_objects
from django.utils.translation import get_language

from core.languages import translation_languages


def set_prefetched(instance, relation, objects):
    """
    Make instance.<relation>.all() return objects instead of the rows in the database.

    This fills Django's prefetch cache, which is not public API; test_translations.py notices when that changes.
    """

    queryset = getattr(instance, relation).all()._chain()
    queryset._result_cache = list(objects)
    queryset._prefetch_done = True
    instance._prefetched_objects_cache = {**instance._prefetched_objects_cache, relation: queryset}


def copy_translations(translations, parent):
    """Save copies of translations for parent, a copy of the object they were made for."""

    relation = parent.translations
    copies = list(translations)

    for translation in copies:
        translation.pk = None
        setattr(translation, relation.field.name, parent)

    relation.model.objects.bulk_create(copies)


class Translatable:
    """
    A model whose texts can be translated.

    translated() returns a copy in another language. The copy shares the primary key of the original, so it refuses to
    be saved: that would store the translation as the source text.
    """

    # The text fields that the model's translations hold
    translated_fields = []
    # The related name of the children translated along with the object
    translated_children = None
    # The language of a translated copy
    translated_into = None

    def save(self, *args, **kwargs):
        if self.translated_into:
            raise ValueError(f'A copy translated into {self.translated_into} cannot be saved')

        super().save(*args, **kwargs)

    @classmethod
    def translation_lookups(cls):
        """The lookups that prefetch the translations of an object and of all its descendants."""

        lookups = ['translations']

        if cls.translated_children:
            child_model = cls._meta.get_field(cls.translated_children).related_model
            lookups += [f'{cls.translated_children}__{lookup}' for lookup in child_model.translation_lookups()]

        return lookups

    def get_translated_texts(self, language):
        """The texts translated into language, by field. Fields holding texts by key give only the translated keys."""

        translations = {translation.language: translation for translation in self.translations.all()}
        texts = {}

        # The base language first, so the texts of a variant win
        for code in reversed(translation_languages(language)):
            if translation := translations.get(code):
                for field in self.translated_fields:
                    value = getattr(translation, field)

                    if isinstance(value, dict):
                        texts[field] = {**texts.get(field, {}), **{key: text for key, text in value.items() if text}}
                    elif value:
                        texts[field] = value

        return texts

    def set_texts(self, texts):
        """Put the translated texts into the fields of this copy."""

        for field, text in texts.items():
            setattr(self, field, text)

    def translated(self, language=None):
        """
        A copy in language, by default the active one, with its children translated as well. Untranslated texts stay in
        the source language.
        """

        language = language or get_language()
        prefetch_related_objects([self], *self.translation_lookups())

        translation = copy.copy(self)
        translation.translated_into = language
        translation.set_texts(self.get_translated_texts(language))

        if self.translated_children:
            children = getattr(self, self.translated_children).all()
            set_prefetched(translation, self.translated_children, [child.translated(language) for child in children])

        return translation
