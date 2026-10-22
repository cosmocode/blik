"""
Answer options of likert and choice questions.

A response stores the id of the option a reviewer chose, never its label, so a label can be reworded or translated
without orphaning the answers already given. Older configs keep the options themselves, see legacy_config.py.
"""

from django.core.validators import EMPTY_VALUES
from django.db import models
from django.utils.translation import gettext_lazy as _

from reviews.models import Response

from .models import AnswerOption

OPTION_TYPES = ['likert', 'single_choice', 'multiple_choice']

# Offered in the source language of the questionnaire a new question belongs to
DEFAULT_LIKERT_SCALE = [_('Strongly Disagree'), _('Disagree'), _('Neutral'), _('Agree'), _('Strongly Agree')]


def save_options(question, rows):
    """Store the option rows the editor posted, [(id or None, label, weight), ...], in their order.

    A row carrying the id of one of the question's options updates that option, so the answers given stay with it.
    Options without a row are deleted.
    """

    existing = {option.id: option for option in question.options.all()}
    kept = [option_id for option_id, label, weight in rows if option_id in existing]
    question.options.exclude(id__in=kept).delete()

    # Move the kept options out of the way of the unique (question, order) pair
    question.options.update(order=models.F('order') + len(existing) + len(rows))

    for order, [option_id, label, weight] in enumerate(rows):
        option = existing.get(option_id)

        if option is None:
            AnswerOption.objects.create(question=question, order=order, label=label, weight=weight)
        else:
            option.order, option.label, option.weight = order, label, weight
            option.save(update_fields=['order', 'label', 'weight', 'updated_at'])


def resolve_answer(options, answer):
    """Map a submitted option id, or an option label, to the option's id, else None."""

    for option in options:
        if f'{answer}' == f'{option.id}':
            return option.id

    for option in options:
        if answer == option.label:
            return option.id

    return None


def resolve_stored_answer(question, options, answer):
    """The id of the option a stored answer names by its label or, for likert answers, by its scale position.

    The demo data generator and API clients stored likert answers as their 1-based position on the scale (4 = "Agree" on
    the default scale).
    """

    for option in options:
        if answer == option.label:
            return option.id

    is_position = isinstance(answer, int) and not isinstance(answer, bool)

    if question.question_type == 'likert' and is_position and 1 <= answer <= len(options):
        return options[answer - 1].id

    return None


def migrate_responses(stdout):
    """Rewrite the labels stored in answer_data to option ids.

    Answers that match no option (the questionnaire was edited after they were given) are kept under 'unmapped' instead
    of being dropped, so the report can still count them.
    """

    mapped = unmapped = 0
    responses = (
        Response.objects.filter(question__question_type__in=OPTION_TYPES)
        .select_related('question')
        .prefetch_related('question__options')
    )

    for response in responses.iterator(chunk_size=500):
        options = list(response.question.options.all())
        data = dict(response.answer_data or {})
        stored = data.get('value')
        answers = stored if isinstance(stored, list) else [stored]
        given = [answer for answer in answers if answer not in EMPTY_VALUES]
        resolved = {answer: resolve_stored_answer(response.question, options, answer) for answer in given}
        ids = [option_id for option_id in resolved.values() if option_id is not None]
        lost = [answer for answer, option_id in resolved.items() if option_id is None]

        if isinstance(stored, list):
            data['value'] = ids
        else:
            data['value'] = ids[0] if ids else None

        if lost:
            data['unmapped'] = lost
            unmapped += 1
            stdout.write(f'  response {response.pk}: no option for {lost!r}')
        else:
            mapped += 1

        response.answer_data = data
        response.save(update_fields=['answer_data'])

    stdout.write(f'Mapped {mapped} response(s), {unmapped} with unmapped answers.')
