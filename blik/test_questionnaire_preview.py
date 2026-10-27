"""The overview's quick preview contains the actual, organization-scoped questions."""
from django.test import TestCase
from django.urls import reverse

from accounts.models import UserProfile
from accounts.permissions import assign_organization_member, ensure_permission_groups
from core.factories import OrganizationFactory, UserFactory
from questionnaires.factories import QuestionFactory, QuestionnaireFactory, QuestionSectionFactory
from questionnaires.models import QuestionTranslation
from questionnaires.answer_options import save_options


class QuestionnaireQuickPreviewTests(TestCase):
    def setUp(self):
        ensure_permission_groups()
        self.org = OrganizationFactory()
        self.user = UserFactory()
        UserProfile.objects.create(user=self.user, organization=self.org)
        assign_organization_member(self.user)
        self.client.force_login(self.user)
        self.questionnaire = QuestionnaireFactory(organization=self.org)
        self.section = QuestionSectionFactory(questionnaire=self.questionnaire, title='Communication')
        self.question = QuestionFactory(
            section=self.section, question_text='Does {name} share knowledge?',
            question_type='rating', config={'min': 1, 'max': 5},
            labels={'1': 'Never', '5': 'Always'}, order=0,
        )
        self.url = reverse('questionnaire_preview', args=[self.questionnaire.uuid])

    def test_member_can_preview_all_questions_and_answers_without_page_chrome(self):
        choice = QuestionFactory(section=self.section, question_type='single_choice',
                                 question_text='Which strength stands out?', order=1)
        save_options(choice, [(None, 'Collaboration', None), (None, 'Planning', None)])
        other = QuestionSectionFactory(questionnaire=self.questionnaire, title='Development')
        QuestionFactory(section=other, question_type='text', question_text='What should Alex improve?')

        response = self.client.get(self.url, {'fragment': 'questions'})

        self.assertEqual(response.headers.get('X-Questionnaire-Preview'), 'questions')
        for text in ['Communication', 'Does Alex share knowledge?', 'Never', 'Always',
                     'Collaboration', 'Planning', 'Development', 'What should Alex improve?']:
            self.assertContains(response, text)
        self.assertNotContains(response, '<html')
        self.assertNotContains(response, '{name}')

    def test_preview_respects_the_selected_language(self):
        QuestionTranslation.objects.create(question=self.question, language='de',
                                           question_text='Teilt {name} Wissen?')
        response = self.client.get(self.url, {'fragment': 'questions', 'lang': 'de'})
        self.assertContains(response, 'Teilt Alex Wissen?')
        self.assertNotContains(response, 'Does Alex share knowledge?')

    def test_rating_preview_includes_unlabelled_values_and_did_not_observe(self):
        self.question.config = {'min': 1, 'max': 5}
        self.question.labels = {'1': 'Never', '5': 'Always'}
        self.question.save()
        response = self.client.get(self.url, {'fragment': 'questions'})
        for value in ('2', '3', '4'):
            self.assertContains(response, f'<li>{value}</li>', html=True)
        self.assertContains(response, 'Did not observe')

    def test_preview_escapes_question_text(self):
        self.question.question_text = '<script>alert("example")</script>'
        self.question.save()
        response = self.client.get(self.url, {'fragment': 'questions'})
        self.assertContains(response, '&lt;script&gt;')
        self.assertNotContains(response, '<script>')

    def test_preview_cannot_read_another_organizations_questionnaire(self):
        other = QuestionnaireFactory()
        response = self.client.get(reverse('questionnaire_preview', args=[other.uuid]),
                                   {'fragment': 'questions'})
        self.assertEqual(response.status_code, 404)

    def test_preview_requires_login(self):
        self.client.logout()
        response = self.client.get(self.url, {'fragment': 'questions'})
        self.assertEqual(response.status_code, 302)
        self.assertNotIn('X-Questionnaire-Preview', response.headers)

    def test_questionnaire_without_sections_has_a_useful_empty_state(self):
        empty = QuestionnaireFactory(organization=self.org)
        response = self.client.get(reverse('questionnaire_preview', args=[empty.uuid]),
                                   {'fragment': 'questions'})
        self.assertContains(response, 'No sections yet')
