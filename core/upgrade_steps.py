"""
Registry of one-time upgrade steps.

Each entry is a (name, callable) tuple. The callable receives a stdout
write-stream for logging. Steps are run in order; only steps not yet
recorded as success=True in the UpgradeStep table will execute.

Old steps should stay in this list forever. If the underlying code is
removed later, replace the callable body with a no-op.
"""
from questionnaires.management.commands.apply_dreyfus_mappings import Command as DreyfusCommand


def _apply_dreyfus_mappings(stdout):
    cmd = DreyfusCommand(stdout=stdout)
    cmd.handle(dry_run=False)


def _reapply_dreyfus_mappings(stdout):
    """Re-run dreyfus mappings to catch any records missed by 0001.

    The fixtures were updated in the same commit as this step, so fresh
    installs get the right data.  For existing deployments the idempotent
    apply_dreyfus_mappings command ensures every DB record is up to date.
    """
    _apply_dreyfus_mappings(stdout)


def _move_setup_admins_into_the_admin_group(stdout):
    """Put admins that hold their permissions directly into the admin group.

    Until this release the setup page granted three permissions straight to
    the first user instead of calling assign_organization_admin(). Those
    accounts are in no group, so every permission added to the group later
    passes them by, and they never got can_delete_organization at all.

    Only accounts holding can_manage_organization directly are touched — the
    per-user grants the team UI writes (a member who may read all reports,
    say) must survive untouched.
    """
    from django.contrib.auth.models import Permission, User
    from django.contrib.contenttypes.models import ContentType

    from accounts.models import UserProfile
    from accounts.permissions import ORG_ADMIN_GROUP, ensure_permission_groups

    admin_group, _ = ensure_permission_groups()
    if admin_group is None:
        stdout.write('  Apps not ready, skipping.')
        return

    content_type = ContentType.objects.get_for_model(UserProfile)
    group_permissions = set(admin_group.permissions.values_list('codename', flat=True))

    candidates = User.objects.filter(
        user_permissions__codename='can_manage_organization',
        user_permissions__content_type=content_type,
    ).exclude(groups__name=ORG_ADMIN_GROUP).distinct()

    moved = 0
    for user in candidates:
        user.groups.add(admin_group)

        # Drop the direct copies the group now provides, so there is one
        # source of truth. Anything else the account holds stays.
        redundant = Permission.objects.filter(
            content_type=content_type,
            codename__in=group_permissions,
        )
        user.user_permissions.remove(*redundant)
        moved += 1
        stdout.write(f'  {user.username} -> {ORG_ADMIN_GROUP}')

    stdout.write(f'Moved {moved} account(s) into {ORG_ADMIN_GROUP}.')


STEPS = [
    ('0001_apply_dreyfus_mappings', _apply_dreyfus_mappings),
    ('0002_reapply_dreyfus_mappings', _reapply_dreyfus_mappings),
    ('0003_move_setup_admins_into_the_admin_group',
     _move_setup_admins_into_the_admin_group),
]
