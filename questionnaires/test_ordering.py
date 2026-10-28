"""The editor saves the order of sections and of the questions in them in one go."""
import json

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from accounts.models import UserProfile
from accounts.permissions import assign_organization_admin, ensure_permission_groups
from core.models import Organization
from questionnaires.models import Question, QuestionSection, Questionnaire


class ReorderTest(TestCase):

    def setUp(self):
        ensure_permission_groups()
        organization = Organization.objects.create(name='Org', email='org@example.com')
        self.admin = User.objects.create_user('admin', 'admin@example.com', 'pw')
        UserProfile.objects.create(user=self.admin, organization=organization)
        assign_organization_admin(self.admin)

        self.questionnaire = Questionnaire.objects.create(name='Q', organization=organization)
        self.first = QuestionSection.objects.create(questionnaire=self.questionnaire, title='First', order=0)
        self.second = QuestionSection.objects.create(questionnaire=self.questionnaire, title='Second', order=1)
        self.a, self.b = [
            Question.objects.create(section=self.first, question_text=text, question_type='text', order=order)
            for order, text in enumerate(['A', 'B'])
        ]
        self.c = Question.objects.create(section=self.second, question_text='C', question_type='text', order=0)

    def reorder(self, layout):
        self.client.force_login(self.admin)

        return self.client.post(
            reverse('questionnaire_edit', args=[self.questionnaire.uuid]),
            {'action': 'reorder', 'layout': json.dumps(layout)},
            headers={'X-Requested-With': 'XMLHttpRequest'},
        )

    def layout(self):
        return [
            (section.title, [question.question_text for question in section.questions.all()])
            for section in self.questionnaire.sections.all()
        ]

    def test_sections_swap_and_a_question_moves_to_another_section(self):
        response = self.reorder([
            {'section': self.second.id, 'questions': [self.b.id, self.c.id]},
            {'section': self.first.id, 'questions': [self.a.id]},
        ])

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.layout(), [('Second', ['B', 'C']), ('First', ['A'])])

    def test_a_layout_missing_a_question_changes_nothing(self):
        response = self.reorder([
            {'section': self.second.id, 'questions': [self.c.id]},
            {'section': self.first.id, 'questions': [self.a.id]},
        ])

        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.layout(), [('First', ['A', 'B']), ('Second', ['C'])])

    def test_questions_of_another_questionnaire_are_refused(self):
        other = Questionnaire.objects.create(name='Other', organization=self.questionnaire.organization)
        stranger = Question.objects.create(
            section=QuestionSection.objects.create(questionnaire=other, title='S', order=0),
            question_text='X',
            question_type='text',
            order=0,
        )

        response = self.reorder([
            {'section': self.first.id, 'questions': [self.a.id, self.b.id, stranger.id]},
            {'section': self.second.id, 'questions': [self.c.id]},
        ])

        self.assertEqual(response.status_code, 400)
        self.assertEqual(Question.objects.get(id=stranger.id).section.questionnaire, other)
