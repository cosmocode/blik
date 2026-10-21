"""
Answer options of likert and choice questions.

A response stores the id of the option a reviewer chose, never its label, so a label can be reworded or translated
without orphaning the answers already given.

Questions saved before answer options existed, the shipped fixtures and older exports keep the options in
`Question.config` instead, as `scale` (likert) or `choices` and `weights`. `move_options_out_of_config()` turns them into
AnswerOption rows.
"""

from django.core.validators import EMPTY_VALUES
from django.db import models

from reviews.models import Response

from .models import AnswerOption, Question

OPTION_TYPES = ['likert', 'single_choice', 'multiple_choice']

DEFAULT_LIKERT_SCALE = ['Strongly Disagree', 'Disagree', 'Neutral', 'Agree', 'Strongly Agree']

# Where older configs keep the options
CONFIG_OPTION_KEYS = ['scale', 'choices', 'weights']


def options_from_config(question):
    """Return [(label, weight), ...] as the config describes them."""

    config = question.config or {}

    if question.question_type == 'likert':
        return [(label, None) for label in config.get('scale', [])]

    choices = config.get('choices', [])
    weights = config.get('weights') or []

    return [(label, weights[index] if index < len(weights) else None) for index, label in enumerate(choices)]


def options_as_config(question):
    """The options in the config keys that clients written before answer options existed read them from."""

    options = list(question.options.all())
    labels = [option.label for option in options]
    weights = [option.weight for option in options]

    if question.question_type == 'likert':
        return {'scale': labels}

    if question.question_type not in OPTION_TYPES:
        return {}

    if any(weight is not None for weight in weights):
        return {'choices': labels, 'weights': weights}

    return {'choices': labels}


def move_options_out_of_config(question):
    """Turn the options a question keeps in its config into AnswerOption rows."""

    config = question.config or {}

    if not any(key in config for key in CONFIG_OPTION_KEYS):
        return

    if question.question_type in OPTION_TYPES:
        options = options_from_config(question)
        AnswerOption.objects.bulk_create([
            AnswerOption(question=question, order=order, label=label, weight=weight)
            for order, [label, weight] in enumerate(options)
        ])

    question.config = {key: value for key, value in config.items() if key not in CONFIG_OPTION_KEYS}
    question.save(update_fields=['config'])


def move_all_options_out_of_config():
    """move_options_out_of_config() for every question that still keeps its options in the config."""

    questions = list(Question.objects.filter(config__has_any_keys=CONFIG_OPTION_KEYS))

    for question in questions:
        move_options_out_of_config(question)

    return len(questions)


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
