"""The Software Engineering fixture gave "Collaboration & Personality" the
primary key of the next section, so migration 0010 created it empty.
"""
from io import StringIO

from django.test import TestCase

from core.factories import OrganizationFactory
from core.upgrade_steps import _fill_the_collaboration_section
from questionnaires.models import QuestionSection

TEXTS = [
    'How well does this person work with the team to solve complex problems?',
    'This person is friendly, approachable, and creates a positive team environment',
    'Additional comments on their collaboration and team dynamics',
]


def collaboration_section(organization=None):
    return QuestionSection.objects.get(
        questionnaire__organization=organization,
        questionnaire__name='Software Engineering 360 Review',
        title='Collaboration & Personality',
    )


def question_texts(section):
    return list(section.questions.order_by('order').values_list('question_text', flat=True))


class CollaborationSectionTests(TestCase):
    def test_new_installs_get_the_questions(self):
        self.assertEqual(question_texts(collaboration_section()), TEXTS)

    def test_step_fills_the_empty_template_section(self):
        section = collaboration_section()
        section.questions.all().delete()

        _fill_the_collaboration_section(StringIO())

        self.assertEqual(question_texts(section), TEXTS)
        rating = section.questions.get(order=1)
        self.assertEqual(rating.config['dreyfus_mapping'], {'agency': 0.5})

    def test_step_leaves_a_filled_section_alone(self):
        _fill_the_collaboration_section(StringIO())

        self.assertEqual(question_texts(collaboration_section()), TEXTS)

    def test_step_leaves_copies_in_organizations_alone(self):
        """Copies are in use: new questions would change running cycles."""
        section = collaboration_section(OrganizationFactory())
        section.questions.all().delete()

        _fill_the_collaboration_section(StringIO())

        self.assertFalse(section.questions.exists())
