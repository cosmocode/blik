"""Deleting a questionnaire — and archiving it when that is impossible.

ReviewCycle.questionnaire is on_delete=PROTECT, so a questionnaire that has
been used cannot be deleted: the delete would raise ProtectedError and the
cycles would lose the questions their answers refer to.
"""
from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from accounts.models import Reviewee, UserProfile
from accounts.permissions import (
    assign_organization_admin,
    assign_organization_member,
    ensure_permission_groups,
)
from core.models import Organization
from questionnaires.factories import QuestionFactory, QuestionSectionFactory
from questionnaires.models import Question, Questionnaire, QuestionSection
from reviews.models import ReviewCycle


class QuestionnaireDeleteTestCase(TestCase):
    def setUp(self):
        ensure_permission_groups()
        self.org = Organization.objects.create(name='Acme', email='org@acme.example')

        self.admin = User.objects.create_user(
            username='admin', email='admin@acme.example', password='pw')
        UserProfile.objects.create(user=self.admin, organization=self.org)
        assign_organization_admin(self.admin)

        self.member = User.objects.create_user(
            username='member', email='member@acme.example', password='pw')
        UserProfile.objects.create(user=self.member, organization=self.org)
        assign_organization_member(self.member)

        self.questionnaire = Questionnaire.objects.create(
            name='Professional Skills', organization=self.org)
        self.section = QuestionSectionFactory(questionnaire=self.questionnaire)
        self.question = QuestionFactory(section=self.section)

        self.reviewee = Reviewee.objects.create(
            organization=self.org, name='Dana Doe', email='dana@acme.example')

    def _url(self, name='questionnaire_delete'):
        return reverse(name, args=[self.questionnaire.id])

    def _use_in_a_cycle(self):
        return ReviewCycle.objects.create(
            reviewee=self.reviewee, questionnaire=self.questionnaire, status='active')


class UnusedQuestionnaireTests(QuestionnaireDeleteTestCase):
    def test_confirmation_page_offers_deletion(self):
        self.client.force_login(self.admin)
        response = self.client.get(self._url())

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Delete Questionnaire')
        self.assertEqual(response.context['cycle_count'], 0)

    def test_it_is_deleted_for_good(self):
        self.client.force_login(self.admin)
        self.client.post(self._url())

        self.assertFalse(Questionnaire.objects.filter(pk=self.questionnaire.pk).exists())

    def test_its_sections_and_questions_go_with_it(self):
        self.client.force_login(self.admin)
        self.client.post(self._url())

        self.assertFalse(QuestionSection.objects.filter(pk=self.section.pk).exists())
        self.assertFalse(Question.objects.filter(pk=self.question.pk).exists())


class UsedQuestionnaireTests(QuestionnaireDeleteTestCase):
    def test_confirmation_page_announces_archiving(self):
        self._use_in_a_cycle()
        self.client.force_login(self.admin)

        response = self.client.get(self._url())

        self.assertEqual(response.context['cycle_count'], 1)
        self.assertContains(response, 'Archive Questionnaire')

    def test_it_is_archived_rather_than_deleted(self):
        self._use_in_a_cycle()
        self.client.force_login(self.admin)

        self.client.post(self._url())

        self.questionnaire.refresh_from_db()
        self.assertFalse(self.questionnaire.is_active)

    def test_the_cycle_keeps_its_questionnaire(self):
        """The whole point of archiving: the report must stay readable."""
        cycle = self._use_in_a_cycle()
        self.client.force_login(self.admin)

        self.client.post(self._url())

        cycle.refresh_from_db()
        self.assertEqual(cycle.questionnaire_id, self.questionnaire.pk)

    def test_no_server_error_where_a_naive_delete_would_raise(self):
        self._use_in_a_cycle()
        self.client.force_login(self.admin)

        response = self.client.post(self._url())

        self.assertRedirects(response, reverse('questionnaire_list'))


class ArchivedQuestionnaireIsOutOfCirculationTests(QuestionnaireDeleteTestCase):
    def setUp(self):
        super().setUp()
        self._use_in_a_cycle()
        self.client.force_login(self.admin)
        self.client.post(self._url())

    def test_it_is_gone_from_the_cycle_form(self):
        response = self.client.get(reverse('review_cycle_create'))
        self.assertNotIn(self.questionnaire, response.context['questionnaires'])

    def test_it_cannot_come_back_through_a_posted_id(self):
        """The form no longer offers it; a hand-made POST must not either."""
        before = ReviewCycle.objects.count()

        self.client.post(
            reverse('quick_cycle_create', args=[self.reviewee.id]),
            {'questionnaire_id': self.questionnaire.id},
        )

        self.assertEqual(ReviewCycle.objects.count(), before)

    def test_the_list_shows_it_as_archived(self):
        response = self.client.get(reverse('questionnaire_list'))

        self.assertNotIn(self.questionnaire, response.context['questionnaires'])
        self.assertIn(self.questionnaire, response.context['archived_questionnaires'])

    def test_it_can_be_restored(self):
        self.client.post(self._url('questionnaire_restore'))

        self.questionnaire.refresh_from_db()
        self.assertTrue(self.questionnaire.is_active)


class QuestionnaireDeletePermissionTests(QuestionnaireDeleteTestCase):
    def test_member_cannot_open_the_confirmation(self):
        self.client.force_login(self.member)
        response = self.client.get(self._url())

        self.assertRedirects(response, reverse('questionnaire_list'))

    def test_member_cannot_delete(self):
        self.client.force_login(self.member)
        self.client.post(self._url())

        self.assertTrue(Questionnaire.objects.filter(pk=self.questionnaire.pk).exists())

    def test_member_cannot_restore(self):
        self.questionnaire.is_active = False
        self.questionnaire.save(update_fields=['is_active'])
        self.client.force_login(self.member)

        self.client.post(self._url('questionnaire_restore'))

        self.questionnaire.refresh_from_db()
        self.assertFalse(self.questionnaire.is_active)

    def test_another_organizations_questionnaire_is_not_reachable(self):
        other_org = Organization.objects.create(name='Other', email='other@example.test')
        foreign = Questionnaire.objects.create(name='Foreign', organization=other_org)
        self.client.force_login(self.admin)

        response = self.client.get(reverse('questionnaire_delete', args=[foreign.id]))

        self.assertEqual(response.status_code, 404)
        self.assertTrue(Questionnaire.objects.filter(pk=foreign.pk).exists())
