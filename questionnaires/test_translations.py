"""Questionnaires are translated text by text; whatever is not translated shows in the source language."""
from django.contrib.auth.models import User
from django.core import mail
from django.test import TestCase
from django.urls import reverse
from django.utils import translation
from rest_framework.test import APIClient

from accounts.models import Reviewee, UserProfile
from accounts.permissions import assign_organization_admin, ensure_permission_groups
from api.models import APIToken
from core.models import Organization
from questionnaires.answer_options import save_options
from questionnaires.models import (
    AnswerOptionTranslation,
    Question,
    QuestionSection,
    QuestionSectionTranslation,
    QuestionTranslation,
    Questionnaire,
    QuestionnaireTranslation,
)
from questionnaires.signals import clone_questionnaire_for_organization
from reviews.models import ReviewCycle, ReviewerToken
from reviews.services import send_reviewer_invitations


class TranslatedQuestionnaireTestCase(TestCase):
    """An English questionnaire, partly translated into German, and its section title also into informal German."""

    def setUp(self):
        ensure_permission_groups()
        self.organization = Organization.objects.create(name='Acme', email='org@acme.example')
        self.admin = User.objects.create_user('admin', 'admin@acme.example', 'pw')
        UserProfile.objects.create(user=self.admin, organization=self.organization)
        assign_organization_admin(self.admin)
        self.questionnaire = Questionnaire.objects.create(name='Skills', organization=self.organization)
        self.section = QuestionSection.objects.create(questionnaire=self.questionnaire, title='Your growth')
        self.rating = Question.objects.create(
            section=self.section,
            question_text='Shares knowledge',
            question_type='rating',
            config={'min': 1, 'max': 5},
            labels={'1': 'Poor', '5': 'Excellent'},
            action_items=[{'key': 'pairing', 'text': 'Pair weekly', 'threshold': 3.5}],
            order=0,
        )
        self.likert = Question.objects.create(
            section=self.section,
            question_text='Listens well',
            question_type='likert',
            order=1,
        )
        save_options(self.likert, [(None, 'Agree', None), (None, 'Disagree', None)])
        agree, disagree = self.likert.options.all()

        QuestionnaireTranslation.objects.create(questionnaire=self.questionnaire, language='de', name='Fähigkeiten')
        QuestionSectionTranslation.objects.create(section=self.section, language='de', title='Ihr Wachstum')
        QuestionSectionTranslation.objects.create(section=self.section, language='de-informal', title='Dein Wachstum')
        QuestionTranslation.objects.create(
            question=self.rating,
            language='de',
            question_text='Teilt Wissen',
            labels={'1': 'Schwach', '9': 'Ohne Gegenstück'},
            action_items={'pairing': 'Wöchentlich zu zweit arbeiten'},
        )
        AnswerOptionTranslation.objects.create(option=agree, language='de', label='Stimme zu')

        self.reviewee = Reviewee.objects.create(name='Dana', email='dana@acme.example', organization=self.organization)
        self.cycle = ReviewCycle.objects.create(reviewee=self.reviewee, questionnaire=self.questionnaire)


class TranslatedCopyTest(TranslatedQuestionnaireTestCase):

    def test_the_copy_has_the_translations_and_the_source_texts_for_the_rest(self):
        questionnaire = self.questionnaire.translated('de')
        [section] = questionnaire.sections.all()
        rating, likert = section.questions.all()
        [action_item] = rating.action_items

        self.assertEqual((questionnaire.name, questionnaire.description), ('Fähigkeiten', ''))
        self.assertEqual(section.title, 'Ihr Wachstum')
        self.assertEqual(rating.question_text, 'Teilt Wissen')
        self.assertEqual(rating.labels, {'1': 'Schwach', '5': 'Excellent'})
        self.assertEqual(action_item['text'], 'Wöchentlich zu zweit arbeiten')
        self.assertEqual(action_item['threshold'], 3.5)
        self.assertEqual(likert.question_text, 'Listens well')
        self.assertEqual([option.label for option in likert.options.all()], ['Stimme zu', 'Disagree'])
        self.assertEqual(likert.options.count(), 2)

    def test_a_variant_takes_its_own_texts_and_those_of_its_base_language(self):
        [section] = self.questionnaire.translated('de-informal').sections.all()
        rating, likert = section.questions.all()

        self.assertEqual(section.title, 'Dein Wachstum')
        self.assertEqual(rating.question_text, 'Teilt Wissen')

    def test_without_a_language_the_active_one_counts(self):
        with translation.override('de'):
            questionnaire = self.questionnaire.translated()

        self.assertEqual(questionnaire.name, 'Fähigkeiten')

    def test_an_untranslated_language_shows_the_source(self):
        [section] = self.questionnaire.translated('en').sections.all()

        self.assertEqual(section.title, 'Your growth')

    def test_the_original_stays_untouched(self):
        self.questionnaire.translated('de')

        [section] = self.questionnaire.sections.all()
        rating, likert = section.questions.all()
        self.assertEqual((self.questionnaire.name, section.title), ('Skills', 'Your growth'))
        self.assertEqual(rating.labels, {'1': 'Poor', '5': 'Excellent'})
        self.assertEqual([option.label for option in likert.options.all()], ['Agree', 'Disagree'])

    def test_a_copy_cannot_be_saved(self):
        questionnaire = self.questionnaire.translated('de')
        [section] = questionnaire.sections.all()

        with self.assertRaises(ValueError):
            questionnaire.save()

        with self.assertRaises(ValueError):
            section.save()

        self.questionnaire.refresh_from_db()
        self.assertEqual(self.questionnaire.name, 'Skills')

    def test_a_clone_keeps_the_source_language_and_the_translations(self):
        self.questionnaire.source_language = 'de-informal'
        self.questionnaire.save()
        other_organization = Organization.objects.create(name='Other', email='org@other.example')

        clone = clone_questionnaire_for_organization(self.questionnaire, other_organization)

        translated = clone.translated('de')
        [section] = translated.sections.all()
        rating, likert = section.questions.all()
        [action_item] = rating.action_items
        self.assertEqual(clone.source_language, 'de-informal')
        self.assertEqual((translated.name, section.title, rating.question_text), (
            'Fähigkeiten', 'Ihr Wachstum', 'Teilt Wissen'))
        self.assertEqual(action_item['text'], 'Wöchentlich zu zweit arbeiten')
        self.assertEqual([option.label for option in likert.options.all()], ['Stimme zu', 'Disagree'])
        self.assertEqual(QuestionTranslation.objects.filter(question__section__questionnaire=clone).count(), 1)


class TranslatedFormTest(TranslatedQuestionnaireTestCase):

    def setUp(self):
        super().setUp()
        self.token = ReviewerToken.objects.create(cycle=self.cycle, category='peer', language='de')

    def test_the_form_is_in_the_reviewers_language(self):
        page = self.client.get(reverse('reviews:feedback_form', args=[self.token.token]))

        for text in ['Ihr Wachstum', 'Teilt Wissen', 'Schwach', 'Excellent', 'Listens well', 'Stimme zu', 'Disagree']:
            self.assertContains(page, text)

        self.assertNotContains(page, 'Shares knowledge')

    def test_errors_quote_the_question_in_the_reviewers_language(self):
        response = self.client.post(reverse('reviews:submit_feedback', args=[self.token.token]))

        errors = ' '.join(response.json()['errors'])
        self.assertIn('Teilt Wissen', errors)
        self.assertNotIn('Shares knowledge', errors)

    def test_invitations_name_the_questionnaire_in_the_reviewers_language(self):
        self.token.reviewer_email = 'reviewer@acme.example'
        self.token.save()

        send_reviewer_invitations(self.cycle)

        [invitation] = mail.outbox
        self.assertIn('Fähigkeiten', invitation.body)
        self.assertNotIn('Skills', invitation.body)


class TranslatedPreviewTest(TranslatedQuestionnaireTestCase):

    def setUp(self):
        super().setUp()
        self.client.force_login(self.admin)

    def preview(self, **params):
        return self.client.get(reverse('questionnaire_preview', args=[self.questionnaire.id]), params)

    def test_the_preview_shows_the_source_language(self):
        page = self.preview()

        self.assertContains(page, 'Shares knowledge')
        self.assertNotContains(page, 'Teilt Wissen')

    def test_the_preview_shows_a_translation(self):
        page = self.preview(lang='de')

        self.assertContains(page, 'Teilt Wissen')
        self.assertContains(page, 'Stimme zu')
        self.assertContains(page, 'aria-current="page">Deutsch (Sie)')

    def test_an_unknown_language_shows_the_source_language(self):
        self.assertContains(self.preview(lang='xx'), 'Shares knowledge')


class TranslatedAPITest(TranslatedQuestionnaireTestCase):

    def setUp(self):
        super().setUp()
        token = APIToken.objects.create(organization=self.organization, created_by=self.admin, name='T')
        self.api = APIClient()
        self.api.credentials(HTTP_AUTHORIZATION=f'Bearer {token.token}')

    def get_question_texts(self, url, **headers):
        [section] = self.api.get(url, **headers).json()['sections']

        return [question['question_text'] for question in section['questions']]

    def test_lang_picks_the_language(self):
        data = self.api.get(f'/api/v1/questionnaires/{self.questionnaire.uuid}/?lang=de').json()
        [section] = data['sections']
        rating, likert = section['questions']

        self.assertEqual((data['name'], data['source_language']), ('Fähigkeiten', 'en'))
        self.assertEqual(section['title'], 'Ihr Wachstum')
        self.assertEqual(rating['question_text'], 'Teilt Wissen')
        self.assertEqual(rating['labels'], {'1': 'Schwach', '5': 'Excellent'})
        self.assertEqual([option['label'] for option in likert['options']], ['Stimme zu', 'Disagree'])

    def test_without_lang_the_browser_language_counts(self):
        url = f'/api/v1/questionnaires/{self.questionnaire.uuid}/'

        texts = self.get_question_texts(url, HTTP_ACCEPT_LANGUAGE='de')

        self.assertEqual(texts, ['Teilt Wissen', 'Listens well'])

    def test_without_lang_and_browser_language_the_organizations_language_counts(self):
        self.organization.default_language = 'de'
        self.organization.save()
        url = f'/api/v1/questionnaires/{self.questionnaire.uuid}/'

        texts = self.get_question_texts(url)

        self.assertEqual(texts, ['Teilt Wissen', 'Listens well'])

    def test_the_list_and_the_cycle_questionnaire_are_translated(self):
        questionnaires = self.api.get('/api/v1/questionnaires/?lang=de').json()['results']
        texts = self.get_question_texts(f'/api/v1/cycles/{self.cycle.uuid}/questionnaire/?lang=de')

        self.assertIn('Fähigkeiten', [questionnaire['name'] for questionnaire in questionnaires])
        self.assertEqual(texts, ['Teilt Wissen', 'Listens well'])

    def test_cycles_keep_the_source_name(self):
        cycle = self.api.get(f'/api/v1/cycles/{self.cycle.uuid}/?lang=de').json()

        self.assertEqual(cycle['questionnaire_detail']['name'], 'Skills')
