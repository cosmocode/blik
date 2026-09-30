"""The organization data export is for organization admins only.

It holds every user and reviewee and the unfiltered report_data of every
cycle, so a member downloading it would read what reports hide from them.
"""
import json

from django.contrib.auth.models import Permission, User
from django.test import TestCase
from django.urls import reverse

from accounts.models import UserProfile
from accounts.permissions import (
    assign_organization_admin,
    assign_organization_member,
    ensure_permission_groups,
)
from core.models import Organization


class ExportPermissionTests(TestCase):
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

    def test_admin_downloads_the_export(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse('account:export_data'))

        self.assertEqual(response.status_code, 200)
        self.assertIn('attachment', response['Content-Disposition'])
        self.assertIn('users', json.loads(response.content))

    def test_member_is_refused(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('account:export_data'))

        self.assertRedirects(response, reverse('settings'))
        self.assertNotIn('Content-Disposition', response)

    def test_report_access_grant_does_not_open_the_export(self):
        """A member allowed to read all reports is still not an admin."""
        self.member.user_permissions.add(
            Permission.objects.get(codename='can_view_all_reports'))

        self.client.force_login(self.member)
        response = self.client.get(reverse('account:export_data'))

        self.assertRedirects(response, reverse('settings'))

    def test_settings_page_offers_the_export_to_admins(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse('settings'))

        self.assertContains(response, reverse('account:export_data'))

    def test_settings_page_hides_the_export_from_members(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('settings'))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, reverse('account:export_data'))
