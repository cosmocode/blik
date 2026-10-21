"""
The texts older configs keep.

Questions saved before answer options and `Question.labels` existed, the shipped fixtures and older exports keep their
texts in `Question.config`: the options as `scale` (likert) or `choices` and `weights`, rating labels as `labels` and
the labels of a scale's ends as `min_label` and `max_label`. `move_texts_out_of_config()` moves them to AnswerOption
rows and `Question.labels`; `config_with_texts()` puts them back for API clients that read the old shape.
"""

from .answer_options import OPTION_TYPES
from .models import AnswerOption, Question

CONFIG_TEXT_KEYS = ['scale', 'choices', 'weights', 'labels', 'min_label', 'max_label']

# The labels of a scale's ends and the config keys older configs keep them under
SCALE_LABEL_KEYS = {'min': 'min_label', 'max': 'max_label'}


def options_from_config(question):
    """Return [(label, weight), ...] as the config describes them."""

    config = question.config or {}

    if question.question_type == 'likert':
        return [(label, None) for label in config.get('scale', [])]

    choices = config.get('choices', [])
    weights = config.get('weights') or []

    return [(label, weights[index] if index < len(weights) else None) for index, label in enumerate(choices)]


def labels_from_config(question):
    """Return the rating or scale labels as the config describes them."""

    config = question.config or {}

    if question.question_type == 'rating':
        return dict(config.get('labels') or {})

    if question.question_type == 'scale':
        return {key: config[config_key] for key, config_key in SCALE_LABEL_KEYS.items() if config.get(config_key)}

    return {}


def move_texts_out_of_config(question):
    """Move the options and labels a question keeps in its config to AnswerOption rows and Question.labels."""

    config = question.config or {}

    if not any(key in config for key in CONFIG_TEXT_KEYS):
        return

    if question.question_type in OPTION_TYPES:
        options = options_from_config(question)
        AnswerOption.objects.bulk_create([
            AnswerOption(question=question, order=order, label=label, weight=weight)
            for order, [label, weight] in enumerate(options)
        ])

    question.labels = labels_from_config(question)
    question.config = {key: value for key, value in config.items() if key not in CONFIG_TEXT_KEYS}
    question.save(update_fields=['config', 'labels'])


def move_all_texts_out_of_config():
    """move_texts_out_of_config() for every question that still keeps texts in its config."""

    questions = list(Question.objects.filter(config__has_any_keys=CONFIG_TEXT_KEYS))

    for question in questions:
        move_texts_out_of_config(question)

    return len(questions)


def config_with_texts(question):
    """The question's config with its options and labels put back in, the shape API clients written before read."""

    config = dict(question.config or {})
    options = list(question.options.all())
    labels = [option.label for option in options]
    weights = [option.weight for option in options]

    if question.question_type == 'likert':
        config['scale'] = labels
    elif question.question_type in OPTION_TYPES:
        config['choices'] = labels

        if any(weight is not None for weight in weights):
            config['weights'] = weights
    elif question.question_type == 'rating' and question.labels:
        config['labels'] = question.labels
    elif question.question_type == 'scale':
        for key, config_key in SCALE_LABEL_KEYS.items():
            if label := question.labels.get(key):
                config[config_key] = label

    return config
