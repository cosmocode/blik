import uuid
from django.db import models
from django.utils.translation import gettext_lazy as _, gettext
from core.models import TimeStampedModel, Organization
from core.managers import QuestionnaireManager


class Questionnaire(TimeStampedModel):
    """Feedback questionnaire"""
    # Public UUID for external references (API, URLs)
    uuid = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False,
        db_index=True,
        help_text=_('Public identifier for API and URL usage (non-enumerable)'),
        verbose_name=_('UUID')
    )

    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name='questionnaires',
        null=True,  # Allow null for existing records and default questionnaires
        blank=True,
        verbose_name=_('organization')
    )
    name = models.CharField(_('name'), max_length=255)
    description = models.TextField(_('description'), blank=True)
    is_default = models.BooleanField(_('default'), default=False)
    is_active = models.BooleanField(_('active'), default=True)

    objects = QuestionnaireManager()

    class Meta:
        verbose_name = _('questionnaire')
        verbose_name_plural = _('questionnaires')
        db_table = 'questionnaires'
        ordering = ['-is_default', 'name']

    def __str__(self):
        return self.name

    @property
    def dreyfus_dimensions(self):
        """Return (has_skill, has_agency) based on question dreyfus_mapping configs.

        A dimension counts as present if any question carries a non-zero weight
        for that dimension in its config['dreyfus_mapping']. Uses the prefetched
        sections/questions relation when available so it doesn't N+1 in list views.
        """
        has_skill = False
        has_agency = False

        for section in self.sections.all():
            for question in section.questions.all():
                mapping = (question.config or {}).get('dreyfus_mapping') or {}
                if not isinstance(mapping, dict):
                    continue
                try:
                    if mapping.get('skill') and float(mapping['skill']) != 0:
                        has_skill = True
                    if mapping.get('agency') and float(mapping['agency']) != 0:
                        has_agency = True
                except (TypeError, ValueError):
                    continue
                if has_skill and has_agency:
                    return has_skill, has_agency

        return has_skill, has_agency

    @property
    def report_type_label(self):
        """Human-readable description of what report this questionnaire produces."""
        has_skill, has_agency = self.dreyfus_dimensions
        if has_skill and has_agency:
            return gettext('Dreyfus (Skill + Agency)')
        if has_skill:
            return gettext('Dreyfus (Skill)')
        if has_agency:
            return gettext('Dreyfus (Agency)')
        return gettext('Standard 360')


class QuestionSection(TimeStampedModel):
    """Section grouping questions within a questionnaire"""
    questionnaire = models.ForeignKey(
        Questionnaire,
        on_delete=models.CASCADE,
        related_name='sections',
        verbose_name=_('questionnaire')
    )
    title = models.CharField(_('title'), max_length=255)
    description = models.TextField(_('description'), blank=True)
    order = models.IntegerField(_('sort order'), default=0)

    class Meta:
        verbose_name = _('section')
        verbose_name_plural = _('sections')
        db_table = 'question_sections'
        ordering = ['questionnaire', 'order']
        unique_together = ['questionnaire', 'order']

    def __str__(self):
        return f"{self.questionnaire.name} - {self.title}"


class Question(TimeStampedModel):
    """Individual question within a section"""

    QUESTION_TYPES = [
        ('rating', _('Rating Scale')),
        ('likert', _('Likert Scale')),
        ('text', _('Free Text')),
        ('single_choice', _('Single Choice')),
        ('multiple_choice', _('Multiple Choice')),
        ('scale', _('Numeric Scale')),
    ]

    # Public UUID for external references (API, URLs)
    uuid = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False,
        db_index=True,
        help_text=_('Public identifier for API and URL usage (non-enumerable)'),
        verbose_name=_('UUID')
    )

    section = models.ForeignKey(
        QuestionSection,
        on_delete=models.CASCADE,
        related_name='questions',
        verbose_name=_('section')
    )
    question_text = models.TextField(_('question text'))
    question_type = models.CharField(_('question type'), max_length=20, choices=QUESTION_TYPES)

    # JSON field for question configuration
    # For rating: {"min": 1, "max": 5, "labels": {"1": "Poor", "5": "Excellent"}}
    # For likert: {"scale": ["Strongly Disagree", "Disagree", "Neutral", "Agree", "Strongly Agree"]}
    # For single_choice:
    #   Basic: {"choices": ["Option 1", "Option 2"]}
    #   With scoring: {"choices": ["Option 1", "Option 2"], "weights": [5, 3], "scoring_enabled": true}
    # For multiple_choice:
    #   Basic: {"choices": ["Option 1", "Option 2"]}
    #   With scoring: {"choices": ["Option 1", "Option 2"], "weights": [5, 3], "scoring_enabled": true}
    #   Note: For multiple_choice, score = sum of selected option weights (rewards selecting more positive attributes)
    # For scale: {"min": 1, "max": 100, "step": 1, "min_label": "Not at all", "max_label": "Extremely"}
    # Optional chart configuration:
    #   "chart_weight": 1.0 (default) - Weight in section average (0.5 = half weight, 2.0 = double weight)
    #   "exclude_from_charts": false (default) - Set true to exclude from chart aggregations
    # Optional Dreyfus model configuration:
    #   "dreyfus_mapping": {"skill": 1.5, "agency": 0.5} - Weights for skill/agency dimensions
    config = models.JSONField(_('configuration'), default=dict)

    # Personalized action items for development plans
    # Format: [
    #   {
    #     "text": "Practice pair programming with senior developers",
    #     "threshold": 3.0,  // Include if question score < threshold
    #     "stages": [1, 2, 3]  // Optional: Relevant Dreyfus stages (1-5)
    #   }
    # ]
    action_items = models.JSONField(_('action items'), default=list, blank=True)

    required = models.BooleanField(_('required'), default=True)
    order = models.IntegerField(_('sort order'), default=0)

    class Meta:
        verbose_name = _('question')
        verbose_name_plural = _('questions')
        db_table = 'questions'
        ordering = ['section', 'order']
        unique_together = ['section', 'order']

    def __str__(self):
        return f"{self.section.title} - {self.question_text[:50]}"
