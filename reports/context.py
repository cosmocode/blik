from statistics import median

from .report_texts import with_texts
from .services import (
    _get_previous_cycle_report,
    _hidden_groups,
    apply_display_anonymization,
    get_report_summary,
)

MEAN = 'mean'
MEDIAN = 'median'
STATISTICS = (MEAN, MEDIAN)
# The question types whose number per group a reader can switch from the mean to the median
MEDIAN_QUESTION_TYPES = ('rating', 'scale')


def display_report_data(report):
    """
    The report data anyone may see: groups below the organization's anonymity
    threshold hidden, with texts. Every reader of report_data goes through this.
    """
    cycle = report.cycle
    threshold = cycle.organization.min_responses_for_anonymity
    anonymized = apply_display_anonymization(report.report_data, min_threshold=threshold)
    _leave_out_trends_from_hidden_previous(anonymized, cycle, threshold)
    return with_texts(anonymized, cycle.questionnaire, cycle.reviewee.name)


def build_report_context(report, *, is_admin_view, statistic=MEAN):
    """
    Template context for the report, shared by the web views and the PDF.

    Anonymize the stored data first: with_texts() adds the texts to insights that
    were calculated without the hidden groups.

    `statistic` picks the number each group shows for a rating or scale question. Strengths, development areas,
    levels and trends are derived from the mean and stay so.
    """
    cycle = report.cycle
    if is_admin_view and not cycle.organization.hide_below_threshold_from_managers:
        # The organization lets managers see the groups below the threshold: the reviewee's report still hides them
        display_data = with_texts(report.report_data, cycle.questionnaire, cycle.reviewee.name)
    else:
        display_data = display_report_data(report)
    _add_scores(display_data, statistic)

    return {
        'cycle': cycle,
        'report': report,
        'report_data': display_data,
        'display_data': display_data,
        'summary': get_report_summary(report),
        'questionnaire': cycle.questionnaire.translated(),
        'is_admin_view': is_admin_view,
        'statistic': statistic,
    }


def answers_median(answers):
    """The median of the numeric answers, or None without any."""
    numbers = [answer for answer in answers if isinstance(answer, (int, float))]
    return float(median(numbers)) if numbers else None


def _add_scores(display_data, statistic):
    """Give each group of a rating or scale question the score it shows: its mean or its median."""
    for section in (display_data.get('by_section') or {}).values():
        for question in (section.get('questions') or {}).values():
            if question.get('question_type') not in MEDIAN_QUESTION_TYPES:
                continue
            for group in (question.get('by_category') or {}).values():
                if group.get('avg') is not None:
                    group['score'] = group['avg'] if statistic == MEAN else answers_median(group.get('responses') or [])


def _leave_out_trends_from_hidden_previous(display_data, cycle, threshold):
    """
    The trends compare with the previous report's stored combined values. When that report
    hides a group, its values include the group's answers, and the change gives them away.
    """
    comparison = display_data.get('comparison') or {}
    if 'overall_trend' not in comparison and 'section_trends' not in comparison:
        return
    previous = _get_previous_cycle_report(cycle)
    if previous and _hidden_groups(previous.report_data, threshold, ['self', 'manager']):
        comparison.pop('overall_trend', None)
        comparison.pop('section_trends', None)
