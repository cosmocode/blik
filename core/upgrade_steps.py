"""
Registry of one-time upgrade steps.

Each entry is a (name, callable) tuple. The callable receives a stdout
write-stream for logging. Steps are run in order; only steps not yet
recorded as success=True in the UpgradeStep table will execute.

Old steps should stay in this list forever. If the underlying code is
removed later, replace the callable body with a no-op.
"""
import json
from pathlib import Path

from django.apps import apps
from django.db import transaction

from questionnaires.action_items import add_action_item_keys
from questionnaires.answer_options import migrate_responses
from questionnaires.legacy_config import move_all_texts_out_of_config
from questionnaires.management.commands.apply_dreyfus_mappings import Command as DreyfusCommand
from questionnaires.models import Question
from questionnaires.shipped import add_shipped_translations


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
    passes them by, and they never got can_delete_organization at all. The
    data import did the same with can_manage_organization alone.

    Only accounts holding can_manage_organization directly are touched. One
    already in the member group was demoted, and assign_organization_member
    used to leave the grant behind: it stays a member and loses the grant.
    Per-user grants the role does not cover (can_view_all_reports, say)
    survive either way.
    """
    from django.contrib.auth.models import User

    from accounts.permissions import (
        ADMIN_ROLE_CODENAMES,
        ORG_ADMIN_GROUP,
        ORG_MEMBER_GROUP,
        _drop_direct_grants,
        assign_organization_admin,
        ensure_permission_groups,
    )

    if ensure_permission_groups() == (None, None):
        # Raise so the runner records a failure and retries next time.
        raise RuntimeError('Apps not ready')

    candidates = User.objects.filter(
        user_permissions__codename='can_manage_organization',
        user_permissions__content_type__app_label='accounts',
    ).exclude(groups__name=ORG_ADMIN_GROUP).distinct()

    moved = demoted = 0
    for user in candidates:
        if user.groups.filter(name=ORG_MEMBER_GROUP).exists():
            _drop_direct_grants(user, ADMIN_ROLE_CODENAMES)
            demoted += 1
            stdout.write(f'  {user.username} stays {ORG_MEMBER_GROUP}')
        else:
            assign_organization_admin(user)
            moved += 1
            stdout.write(f'  {user.username} -> {ORG_ADMIN_GROUP}')

    stdout.write(f'Moved {moved} account(s) into {ORG_ADMIN_GROUP}, '
                 f'removed stale admin grants from {demoted} member(s).')


def _fill_the_collaboration_section(stdout):
    """Add the questions of "Collaboration & Personality" to the Software
    Engineering template.

    The fixture gave that section the primary key of the next one, so
    migration 0010 created it without its three questions. Only the
    template gets them: copies in organizations are in use, and new
    questions would change cycles that are already running.
    """
    from questionnaires.models import Question, Questionnaire, QuestionSection

    title = 'Collaboration & Personality'
    fixture_path = (Path(apps.get_app_config('questionnaires').path)
                    / 'fixtures' / 'software_engineering_questionnaire.json')
    fixture = json.loads(fixture_path.read_text())

    [section_pk] = [
        item['pk'] for item in fixture
        if item['model'] == 'questionnaires.questionsection'
        and item['fields']['title'] == title
    ]
    questions = [
        item['fields'] for item in fixture
        if item['model'] == 'questionnaires.question'
        and item['fields']['section'] == section_pk
    ]

    sections = list(QuestionSection.objects.filter(
        questionnaire__in=Questionnaire.objects.templates(),
        questionnaire__name='Software Engineering 360 Review',
        title=title,
        questions__isnull=True,
    ))

    for section in sections:
        for fields in questions:
            Question.objects.create(
                section=section,
                question_text=fields['question_text'],
                question_type=fields['question_type'],
                config=fields['config'],
                required=fields['required'],
                order=fields['order'],
            )

    stdout.write(f'Added {len(questions)} question(s) to {len(sections)} '
                 f'empty {title} section(s).')


def move_question_texts(stdout):
    """Move the options and labels of questions out of their config and point the answers at the options.

    Runs in one transaction: a converted answer holds an option id, which a second run would take for a likert scale
    position, so a step that fails halfway must leave everything as it was.
    """

    with transaction.atomic():
        count = move_all_texts_out_of_config()
        stdout.write(f'Moved the texts of {count} question(s) out of their config.')
        migrate_responses(stdout)


def key_action_items(stdout):
    """Give every action item a key, which a translation of the item refers to."""

    questions = Question.objects.exclude(action_items=[])

    for question in questions:
        question.action_items = add_action_item_keys(question.action_items)
        question.save(update_fields=['action_items'])

    count = len(questions)
    stdout.write(f'Keyed the action items of {count} question(s).')


def translate_shipped_questionnaires(stdout):
    """Put {name} into the questions of the questionnaires made from a shipped template and add their translations."""

    count = add_shipped_translations()
    stdout.write(f'Translated {count} questionnaire(s) made from a shipped template.')


STEPS = [
    ('0001_apply_dreyfus_mappings', _apply_dreyfus_mappings),
    ('0002_reapply_dreyfus_mappings', _reapply_dreyfus_mappings),
    ('0003_move_setup_admins_into_the_admin_group',
     _move_setup_admins_into_the_admin_group),
    ('0004_fill_the_collaboration_section', _fill_the_collaboration_section),
    ('0005_move_question_texts', move_question_texts),
    ('0006_key_action_items', key_action_items),
    ('0007_translate_shipped_questionnaires', translate_shipped_questionnaires),
]
