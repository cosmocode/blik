"""An imported admin must be the same admin as one created any other way.

The import used to grant can_manage_organization alone, straight to the
user: no group, none of the other admin permissions, and nothing added to
the Organization Admin group later.
"""
from django.contrib.auth.models import User
from django.test import TestCase

from accounts.import_service import import_users
from accounts.permissions import ORG_ADMIN_GROUP, ensure_permission_groups
from core.models import Organization


class ImportedAdminTests(TestCase):
    def setUp(self):
        ensure_permission_groups()
        self.org = Organization.objects.create(name='Acme', email='org@acme.example')

    def _import(self, **user_data):
        return import_users(self.org, [{
            'username': 'imported',
            'email': 'imported@acme.example',
            **user_data,
        }])

    def test_imported_admin_lands_in_the_admin_group(self):
        result = self._import(is_org_admin=True)

        self.assertEqual(result['errors'], [])
        user = User.objects.get(username='imported')
        self.assertTrue(user.groups.filter(name=ORG_ADMIN_GROUP).exists())
        self.assertFalse(user.user_permissions.exists())
        self.assertTrue(user.has_perm('accounts.can_invite_members'))
        self.assertTrue(user.has_perm('accounts.can_delete_organization'))

    def test_imported_member_gets_no_admin_rights(self):
        self._import(is_org_admin=False)

        user = User.objects.get(username='imported')
        self.assertFalse(user.groups.filter(name=ORG_ADMIN_GROUP).exists())
        self.assertFalse(user.has_perm('accounts.can_manage_organization'))
