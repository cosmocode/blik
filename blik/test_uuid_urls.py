"""Questionnaire and reviewee pages are addressed by UUID and scoped to the
user's organization. Old integer-id URLs redirect to the UUID URLs."""
from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from accounts.models import Reviewee, UserProfile
from accounts.permissions import assign_organization_admin, ensure_permission_groups
from core.models import Organization
from questionnaires.models import Questionnaire


class UuidUrlTestCase(TestCase):
    def setUp(self):
        ensure_permission_groups()
        self.org = Organization.objects.create(name='Acme', email='org@acme.example')
        self.other_org = Organization.objects.create(name='Other', email='org@other.example')

        self.admin = User.objects.create_user(
            username='admin', email='admin@acme.example', password='pw')
        UserProfile.objects.create(user=self.admin, organization=self.org)
        assign_organization_admin(self.admin)
        self.client.force_login(self.admin)

        self.questionnaire = Questionnaire.objects.create(name='Ours', organization=self.org)
        self.foreign_questionnaire = Questionnaire.objects.create(
            name='Theirs', organization=self.other_org)
        self.reviewee = Reviewee.objects.create(
            organization=self.org, name='Dana Doe', email='dana@acme.example')
        self.foreign_reviewee = Reviewee.objects.create(
            organization=self.other_org, name='Eve Roe', email='eve@other.example')


class LegacyIdRedirectTests(UuidUrlTestCase):
    def test_questionnaire_pages_redirect_permanently_to_the_uuid_url(self):
        for suffix, name in [
            ('edit', 'questionnaire_edit'),
            ('delete', 'questionnaire_delete'),
            ('preview', 'questionnaire_preview'),
            ('sample-report', 'questionnaire_sample_report'),
        ]:
            with self.subTest(suffix=suffix):
                response = self.client.get(
                    f'/dashboard/questionnaires/{self.questionnaire.id}/{suffix}/')
                self.assertRedirects(
                    response, reverse(name, args=[self.questionnaire.uuid]),
                    status_code=301, fetch_redirect_response=False)

    def test_reviewee_pages_redirect_permanently_to_the_uuid_url(self):
        for suffix, name in [('edit', 'reviewee_edit'), ('delete', 'reviewee_delete')]:
            with self.subTest(suffix=suffix):
                response = self.client.get(f'/dashboard/reviewees/{self.reviewee.id}/{suffix}/')
                self.assertRedirects(
                    response, reverse(name, args=[self.reviewee.uuid]),
                    status_code=301, fetch_redirect_response=False)

    def test_another_organizations_questionnaire_is_not_found(self):
        response = self.client.get(
            f'/dashboard/questionnaires/{self.foreign_questionnaire.id}/preview/')
        self.assertEqual(response.status_code, 404)

    def test_another_organizations_reviewee_is_not_found(self):
        response = self.client.get(f'/dashboard/reviewees/{self.foreign_reviewee.id}/edit/')
        self.assertEqual(response.status_code, 404)


class OrganizationScopeTests(UuidUrlTestCase):
    def test_preview_shows_own_questionnaire(self):
        response = self.client.get(reverse('questionnaire_preview', args=[self.questionnaire.uuid]))
        self.assertEqual(response.status_code, 200)

    def test_preview_hides_another_organizations_questionnaire(self):
        response = self.client.get(
            reverse('questionnaire_preview', args=[self.foreign_questionnaire.uuid]))
        self.assertEqual(response.status_code, 404)

    def test_sample_report_hides_another_organizations_questionnaire(self):
        response = self.client.get(
            reverse('questionnaire_sample_report', args=[self.foreign_questionnaire.uuid]))
        self.assertEqual(response.status_code, 404)

    def test_preview_hides_builtin_template_questionnaires(self):
        template = Questionnaire.objects.create(name='Template', organization=None, is_default=True)
        response = self.client.get(reverse('questionnaire_preview', args=[template.uuid]))
        self.assertEqual(response.status_code, 404)

    def test_reviewee_edit_hides_another_organizations_reviewee(self):
        response = self.client.post(
            reverse('reviewee_edit', args=[self.foreign_reviewee.uuid]),
            {'name': 'Renamed', 'email': 'eve@other.example'})

        self.assertEqual(response.status_code, 404)
        self.foreign_reviewee.refresh_from_db()
        self.assertEqual(self.foreign_reviewee.name, 'Eve Roe')

    def test_reviewee_delete_hides_another_organizations_reviewee(self):
        response = self.client.post(reverse('reviewee_delete', args=[self.foreign_reviewee.uuid]))

        self.assertEqual(response.status_code, 404)
        self.foreign_reviewee.refresh_from_db()
        self.assertTrue(self.foreign_reviewee.is_active)
