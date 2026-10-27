"""account:settings rendered account/settings.html, a template that never
existed. The account settings live on the dashboard settings page."""
from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from accounts.models import UserProfile
from accounts.permissions import assign_organization_admin
from core.models import Organization


class AccountSettingsTests(TestCase):
    def setUp(self):
        org = Organization.objects.create(name='Acme', email='org@acme.example')
        self.admin = User.objects.create_user(username='admin', email='a@acme.example', password='pw')
        UserProfile.objects.create(user=self.admin, organization=org)
        assign_organization_admin(self.admin)
        self.client.force_login(self.admin)

    def test_account_settings_redirects_to_dashboard_settings(self):
        resp = self.client.get(reverse('account:settings'))
        self.assertRedirects(resp, reverse('settings'), fetch_redirect_response=False)

    def test_wrong_password_on_delete_account_returns_to_settings(self):
        resp = self.client.post(reverse('account:delete_account'), {'password': 'wrong'})
        self.assertRedirects(resp, reverse('settings'), fetch_redirect_response=False)
        self.assertTrue(User.objects.filter(pk=self.admin.pk).exists())
