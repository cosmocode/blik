"""Emails about an organization's subscription: trial reminders, confirmations, pause and cancellation.

Stripe sends receipts, failed-payment and card-expiry emails. These emails only tell the customer
what changed in Blik and what to do next.
"""
import logging
from datetime import timedelta

from django.conf import settings
from django.template.loader import render_to_string
from django.utils import timezone, translation
from django.utils.formats import date_format
from django.utils.translation import gettext as _

from accounts.models import Reviewee, UserProfile
from core.email import send_email
from core.languages import recipient_language, user_language
from core.url import get_absolute_url
from reviews.models import ReviewCycle, ReviewerToken

logger = logging.getLogger(__name__)

SUPPORT_EMAIL = 'support@blik360.com'

# Days we keep an organization's data after its subscription ends (see the pricing page).
DATA_RETENTION_DAYS = 30


def billing_recipients(organization):
    """(user, email) for each active administrator of the organization; the organization's email if it has none."""
    profiles = UserProfile.objects.filter(
        organization=organization, user__is_active=True,
    ).select_related('user')
    admins = [p.user for p in profiles
              if p.user.email and p.user.has_perm('accounts.can_manage_organization')]

    if admins:
        return [(user, user.email) for user in admins]
    return [(None, organization.email)] if organization.email else []


def _send(subscription, template, subject, context, dates):
    """Render and send one email per billing recipient, each in their own language.

    subject is a function of the context. dates maps context names to datetimes, which are formatted
    in each recipient's language.
    """
    organization = subscription.organization
    sent = 0

    for user, email in billing_recipients(organization):
        language = user_language(user, organization) if user else recipient_language(organization=organization)

        with translation.override(language):
            full_context = {
                'site_name': settings.SITE_NAME,
                'organization': organization,
                'subscription': subscription,
                'plan': subscription.plan,
                'support_email': SUPPORT_EMAIL,
                'user': user,
                **context,
            }
            for name, value in dates.items():
                full_context[name] = date_format(timezone.localtime(value), 'DATE_FORMAT') if value else None

            sent += send_email(
                subject=subject(full_context),
                message=render_to_string(f'emails/{template}.txt', full_context),
                recipient_list=[email],
                html_message=render_to_string(f'emails/{template}.html', full_context),
            )

    return sent


def _usage(organization):
    """What the organization set up so far. Counts only, so nothing tells who reviewed whom."""
    cycles = ReviewCycle.objects.filter(reviewee__organization=organization)

    return {
        'cycle_count': cycles.count(),
        'reviewee_count': Reviewee.objects.filter(organization=organization, is_active=True).count(),
        'completed_review_count': ReviewerToken.objects.filter(
            cycle__in=cycles, completed_at__isnull=False).count(),
        'member_count': UserProfile.objects.filter(organization=organization).count(),
    }


def send_trial_ending_email(subscription, days):
    """The reminder that the trial ends soon. days is 3 or 1: which reminder this is."""
    context = {
        'days': days,
        'choose_plan_url': get_absolute_url('subscriptions:billing_portal'),
        'create_cycle_url': get_absolute_url('review_cycle_create'),
        **_usage(subscription.organization),
    }

    def subject(c):
        values = {'site_name': c['site_name'], 'date': c['trial_end_date']}
        if days == 1:
            return _('Last reminder: your %(site_name)s trial ends on %(date)s') % values
        return _('Your %(site_name)s trial ends on %(date)s') % values

    return _send(subscription, 'trial_ending', subject, context, {'trial_end_date': subscription.trial_end})


def send_trial_ended_email(subscription):
    """The trial ended and the first payment did not go through, so the account is paused."""
    context = {
        'reactivate_url': get_absolute_url('subscriptions:billing_portal'),
        **_usage(subscription.organization),
    }

    def subject(c):
        return _('Your %(site_name)s trial has ended') % {'site_name': c['site_name']}

    return _send(subscription, 'trial_ended', subject, context, {})


def send_subscription_confirmed_email(subscription, kind):
    """kind: 'started' (trial started), 'active' (paid plan runs), 'plan_changed' or 'resumed' (cancellation undone)."""
    if kind == 'started' and subscription.status != 'trialing':
        kind = 'active'  # A subscription that started without a trial
    context = {
        'kind': kind,
        'dashboard_url': get_absolute_url('admin_dashboard'),
    }

    def subject(c):
        values = {'site_name': c['site_name'], 'plan': c['plan'].name}
        if kind == 'started':
            return _('Your %(site_name)s trial has started') % values
        if kind == 'plan_changed':
            return _('Your %(site_name)s plan is now %(plan)s') % values
        if kind == 'resumed':
            return _('Your %(site_name)s subscription continues') % values
        return _('Your %(site_name)s subscription is active') % values

    return _send(subscription, 'subscription_confirmed', subject, context, {
        'trial_end_date': subscription.trial_end if subscription.status == 'trialing' else None,
        'period_end_date': subscription.current_period_end,
    })


def send_cancellation_email(subscription):
    """The subscription is canceled: at the end of the current period, or it has already ended."""
    ended = subscription.status == 'canceled'
    end = (subscription.canceled_at or timezone.now()) if ended else subscription.current_period_end
    context = {
        'ended': ended,
        'retention_days': DATA_RETENTION_DAYS,
        'settings_url': get_absolute_url('settings'),
        'export_url': get_absolute_url('account:export_data'),
    }

    def subject(c):
        if ended:
            return _('Your %(site_name)s subscription has ended') % {'site_name': c['site_name']}
        return _('Your %(site_name)s subscription is canceled') % {'site_name': c['site_name']}

    return _send(subscription, 'subscription_canceled', subject, context, {
        'end_date': end,
        'deletion_date': end + timedelta(days=DATA_RETENTION_DAYS),
    })


def snapshot(subscription):
    """The state that decides which email a change needs. Take it before the subscription changes."""
    return subscription.status, subscription.cancel_at_period_end, subscription.plan_id


def change_email(before, subscription):
    """Which email the change from `before` (a snapshot) to the subscription's state needs, or None."""
    old_status, old_cancel, old_plan_id = before

    if old_status == 'trialing' and subscription.status in ('past_due', 'unpaid', 'paused') and not old_cancel:
        return 'trial_ended'
    if subscription.cancel_at_period_end and not old_cancel and subscription.is_active:
        return 'canceled'
    if old_cancel and not subscription.cancel_at_period_end and subscription.is_active:
        return 'resumed'
    if subscription.status == 'active' and old_status != 'active':
        return 'active'
    if subscription.plan_id != old_plan_id and subscription.is_active:
        return 'plan_changed'
    return None


def notify_change(before, subscription):
    """Send the email that the change from `before` needs, if any.

    A failed email is logged, not raised: the change is already saved, and a retried webhook would
    not see it again.
    """
    kind = change_email(before, subscription)

    try:
        if kind == 'trial_ended':
            send_trial_ended_email(subscription)
        elif kind == 'canceled':
            send_cancellation_email(subscription)
        elif kind:
            send_subscription_confirmed_email(subscription, kind)
    except Exception:
        logger.exception('Subscription %s changed (%s) but its email failed', subscription.pk, kind)

    return kind


def send_trial_reminders(dry_run=False, now=None):
    """Send the 3-day and 1-day trial-ending reminders that are due. Runs daily; each reminder goes out once.

    A subscription that is canceled at the end of its trial gets no reminder, because nothing will be
    charged. A 3-day reminder that is still unsent when a day or less is left is skipped: the 1-day
    reminder replaces it.
    """
    from .models import Subscription

    now = now or timezone.now()
    stats = {'eligible': 0, 'sent': 0, 'errors': []}

    trials = Subscription.objects.filter(
        status='trialing', cancel_at_period_end=False,
        trial_end__gt=now, trial_end__lte=now + timedelta(days=3),
    ).select_related('organization', 'plan')

    for subscription in trials:
        if subscription.trial_end - now <= timedelta(days=1):
            days, field = 1, 'trial_reminder_1_day_sent_at'
        else:
            days, field = 3, 'trial_reminder_3_days_sent_at'

        if getattr(subscription, field):
            continue

        stats['eligible'] += 1
        if dry_run:
            continue

        try:
            send_trial_ending_email(subscription, days)
        except Exception as e:
            stats['errors'].append(f'Trial reminder for subscription {subscription.pk} failed: {e}')
            continue

        setattr(subscription, field, now)
        subscription.save(update_fields=[field])
        stats['sent'] += 1

    return stats
