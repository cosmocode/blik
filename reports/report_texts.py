"""
The texts of a report, in the active language.

Reports of the current schema store codes and numbers. with_texts() adds the texts the report templates show, under the
keys in which reports of schema 1 stored them in English. Reports of schema 1 keep their English texts.
"""

import copy

from django.utils import translation
from django.utils.formats import number_format
from django.utils.translation import gettext_lazy as _

from .dreyfus_service import (
    DREYFUS_STAGES,
    agency_profile_with_texts,
    development_plan_with_texts,
    quadrant_with_texts,
    skill_profile_with_texts,
)
from .services import (
    GAP_IMPOSTER_SYNDROME,
    GAP_OVERCONFIDENCE,
    RATING_DEVELOPING,
    RATING_EXCELLENT,
    RATING_NEEDS_SUPPORT,
    RATING_OUTSTANDING,
    RATING_STRONG,
    REPORT_SCHEMA,
    TREND_DOWN,
    TREND_SLIGHT_DOWN,
    TREND_SLIGHT_UP,
    TREND_STABLE,
    TREND_UP,
)

# Symbol and label of a trend by its direction
TRENDS = {
    TREND_UP: ('↑', _('Improved')),
    TREND_SLIGHT_UP: ('↗', _('Slightly improved')),
    TREND_STABLE: ('→', _('Stable')),
    TREND_SLIGHT_DOWN: ('↘', _('Slightly declined')),
    TREND_DOWN: ('↓', _('Declined')),
}

# Message and interpretation of a perception gap by its type
PERCEPTION_GAPS = {
    GAP_IMPOSTER_SYNDROME: (
        _("Self-assessment (%(self)s) significantly lower than others' perception (%(others)s)"),
        _('Strong performance but may undervalue own contributions'),
    ),
    GAP_OVERCONFIDENCE: (
        _("Self-assessment (%(self)s) higher than others' perception (%(others)s)"),
        _('Opportunity to align self-perception with team feedback'),
    ),
}

# The overall ratings with the average scores they cover
RATING_RANGES = {
    RATING_OUTSTANDING: _('Outstanding (4.5+)'),
    RATING_EXCELLENT: _('Excellent (4.0-4.4)'),
    RATING_STRONG: _('Strong (3.5-3.9)'),
    RATING_DEVELOPING: _('Developing (3.0-3.4)'),
    RATING_NEEDS_SUPPORT: _('Needs Support (below 3.0)'),
}

RATINGS = {
    RATING_OUTSTANDING: _('Outstanding'),
    RATING_EXCELLENT: _('Excellent'),
    RATING_STRONG: _('Strong'),
    RATING_DEVELOPING: _('Developing'),
    RATING_NEEDS_SUPPORT: _('Needs Support'),
}


def stage_key(name):
    """The key of the Dreyfus stage that a report of schema 1 names in English."""

    with translation.override('en'):
        keys = {str(stage['name']): stage['key'] for stage in DREYFUS_STAGES.values()}

    return keys.get(name)


def with_texts(report_data):
    """A copy of report_data with the texts its codes stand for."""

    data = copy.deepcopy(report_data)
    insights = data.get('insights') or {}
    skill_profile = insights.get('skill_profile')

    if data.get('schema') != REPORT_SCHEMA:
        if skill_profile:
            skill_profile['stage_key'] = stage_key(skill_profile.get('skill_stage'))

        return data

    comparison = data.get('comparison') or {}
    trends = [comparison.get('overall_trend'), *(comparison.get('section_trends') or {}).values()]

    for trend in trends:
        if trend:
            symbol, label = TRENDS[trend['direction']]
            trend.update(symbol=symbol, label=str(label))

    for gap in insights.get('perception_gaps') or []:
        message, interpretation = PERCEPTION_GAPS[gap['type']]
        # number_format() cuts off further decimals instead of rounding them
        scores = {
            'self': number_format(round(gap['self_score'], 1), 1),
            'others': number_format(round(gap['others_score'], 1), 1),
        }
        gap.update(message=message % scores, interpretation=str(interpretation))

    if sentiment := insights.get('overall_sentiment'):
        sentiment['rating'] = str(RATINGS[sentiment['rating']])

    if skill_profile:
        insights['skill_profile'] = skill_profile_with_texts(skill_profile)

    if agency_profile := insights.get('agency_profile'):
        insights['agency_profile'] = agency_profile_with_texts(agency_profile)

    if quadrant := insights.get('dreyfus_quadrant'):
        insights['dreyfus_quadrant'] = quadrant_with_texts(quadrant)

    if (plan := insights.get('development_plan')) and skill_profile:
        insights['development_plan'] = development_plan_with_texts(plan, skill_profile)

    return data
