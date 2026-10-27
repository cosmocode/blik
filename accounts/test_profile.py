import uuid

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.factories import RevieweeFactory, UserProfileFactory
from accounts.models import Reviewee
from core.factories import OrganizationFactory, UserFactory
from questionnaires.factories import QuestionnaireFactory
from reports.models import Report
from reviews.factories import ReviewCycleFactory
from reviews.models import ReviewerToken


class ProfilePageTests(TestCase):
    def setUp(self):
        self.profile = UserProfileFactory(user__email='member@example.test')
        self.user = self.profile.user
        self.organization = self.profile.organization
        self.client.force_login(self.user)

    def post_profile(self, **changes):
        data = {'first_name': 'Alex', 'last_name': 'Taylor',
                'email': self.user.email, 'language': ''}
        data.update(changes)
        return self.client.post(reverse('profile'), data)

    def test_invalid_language_is_explained_and_values_are_preserved(self):
        response = self.post_profile(language='unsupported')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, response.context['form'].errors['language'][0])
        self.assertContains(response, 'value="Alex"')

    def test_duplicate_email_is_explained_without_saving(self):
        other = UserFactory(email='taken@example.test')
        response = self.post_profile(email=other.email)
        self.assertContains(response, 'This email address is already in use.')
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, 'member@example.test')

    def test_saves_personal_details_and_language_without_changing_username(self):
        username = self.user.username
        response = self.post_profile(email='updated@example.test', language='de', username='changed')
        self.assertRedirects(response, reverse('profile'), fetch_redirect_response=False)
        self.user.refresh_from_db()
        self.profile.refresh_from_db()
        self.assertEqual((self.user.first_name, self.user.last_name), ('Alex', 'Taylor'))
        self.assertEqual(self.user.email, 'updated@example.test')
        self.assertEqual(self.profile.language, 'de')
        self.assertEqual(self.user.username, username)

    def test_empty_history(self):
        response = self.client.get(reverse('profile'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'No review cycles found for your account.')

    def test_form_labels_follow_profile_language(self):
        for language in ('de', 'de-informal'):
            with self.subTest(language=language):
                self.profile.language = language
                self.profile.save(update_fields=['language'])
                response = self.client.get(reverse('profile'))
                self.assertContains(response, '>Vorname</label>')
                self.assertContains(response, '>Nachname</label>')
                self.assertContains(response, '>E-Mail</label>')
                self.assertContains(response, '>Sprache</label>')

    def test_only_completed_reports_are_linked(self):
        reviewee = Reviewee.objects.get(organization=self.organization, email=self.user.email)
        reports = []
        for status in ('active', 'completed'):
            cycle = ReviewCycleFactory(reviewee=reviewee, status=status,
                questionnaire=QuestionnaireFactory(organization=self.organization))
            reports.append(Report.objects.create(cycle=cycle, report_data={}, access_token=uuid.uuid4()))
        ReviewCycleFactory(reviewee=reviewee, status='completed',
            questionnaire=QuestionnaireFactory(organization=self.organization))
        response = self.client.get(reverse('profile'))
        self.assertContains(response, reverse('reports:reviewee_report', args=[reports[1].access_token]))
        self.assertNotContains(response, reverse('reports:reviewee_report', args=[reports[0].access_token]))
        self.assertEqual(len(response.context['cycles_with_reports']), 3)

    def test_active_cycle_offers_self_assessment_until_it_is_done(self):
        cycle = ReviewCycleFactory(
            reviewee=Reviewee.objects.get(organization=self.organization, email=self.user.email),
            questionnaire=QuestionnaireFactory(organization=self.organization))
        self_link = reverse('reviews:claim_token', args=[cycle.invitation_token_self])
        detail_link = reverse('review_cycle_detail', args=[cycle.uuid])

        response = self.client.get(reverse('profile'))
        self.assertContains(response, self_link)
        self.assertContains(response, detail_link)

        ReviewerToken.objects.create(cycle=cycle, category='self', completed_at=timezone.now())
        response = self.client.get(reverse('profile'))
        self.assertNotContains(response, self_link)
        self.assertContains(response, detail_link)
        self.assertEqual(self.client.get(detail_link).status_code, 200)

    def test_history_is_scoped_to_current_reviewee_and_organization(self):
        own = ReviewCycleFactory(
            reviewee=Reviewee.objects.get(organization=self.organization, email=self.user.email),
            questionnaire=QuestionnaireFactory(organization=self.organization, name='My feedback cycle'))
        other_org = OrganizationFactory()
        ReviewCycleFactory(reviewee=RevieweeFactory(organization=other_org, email=self.user.email),
            questionnaire=QuestionnaireFactory(organization=other_org, name='Private other organization'))
        ReviewCycleFactory(reviewee=RevieweeFactory(organization=self.organization, email='other@example.test'),
            questionnaire=QuestionnaireFactory(organization=self.organization, name='Private other person'))
        response = self.client.get(reverse('profile'))
        self.assertEqual([item['cycle'] for item in response.context['cycles_with_reports']], [own])
        self.assertNotContains(response, 'Private other organization')
        self.assertNotContains(response, 'Private other person')

    def test_requires_login(self):
        self.client.logout()
        response = self.client.get(reverse('profile'))
        self.assertEqual(response.status_code, 302)
        self.assertIn('login', response.url)
