"""user_passes_test sent logged-in users who are not superusers to the
login page, which sends logged-in users back to `next`: a redirect loop."""
from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from accounts.models import UserProfile
from accounts.permissions import assign_organization_admin
from core.models import Organization


class SuperuserCreateOrganizationTests(TestCase):
    def test_org_admin_is_sent_to_the_dashboard(self):
        org = Organization.objects.create(name='Acme', email='org@acme.example')
        admin = User.objects.create_user(username='admin', email='a@acme.example', password='pw')
        UserProfile.objects.create(user=admin, organization=org)
        assign_organization_admin(admin)
        self.client.force_login(admin)

        resp = self.client.get(reverse('superuser_create_organization'))

        self.assertRedirects(resp, reverse('admin_dashboard'), fetch_redirect_response=False)
