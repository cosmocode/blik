"""
Custom email utilities that use Organization SMTP settings
"""
import logging

from django.core.mail import EmailMultiAlternatives, get_connection
from django.core.mail.backends.smtp import EmailBackend
from django.conf import settings
from django.utils import translation
from django.utils.translation import gettext as _, gettext_lazy
from .languages import user_language
from .models import Organization

logger = logging.getLogger(__name__)


def get_email_backend():
    """
    Get email backend configured with Organization SMTP settings.
    Falls back to the backend in Django settings if no organization SMTP host
    is configured — that fallback must honour EMAIL_BACKEND, otherwise console
    and locmem (test) backends are bypassed in favour of a real SMTP connection.
    """
    try:
        org = Organization.objects.filter(is_active=True).first()

        if org and org.smtp_host:
            # Use organization's SMTP settings
            return EmailBackend(
                host=org.smtp_host,
                port=org.smtp_port,
                username=org.smtp_username,
                password=org.smtp_password,
                use_tls=org.smtp_use_tls,
                fail_silently=False,
            )
    except Exception:
        logger.exception('Error loading organization email settings')

    return get_connection(fail_silently=False)


def get_from_email():
    """Get the from_email from Organization or fall back to Django settings"""
    try:
        org = Organization.objects.filter(is_active=True).first()
        if org and org.from_email:
            return org.from_email
    except Exception:
        pass

    return settings.DEFAULT_FROM_EMAIL


def send_email(subject, message, recipient_list, html_message=None, from_email=None):
    """
    Send email using Organization SMTP settings.

    Args:
        subject: Email subject
        message: Plain text message
        recipient_list: List of recipient email addresses
        html_message: Optional HTML version of message
        from_email: Optional from email (defaults to organization setting)

    Returns:
        Number of emails sent (0 or 1)
    """
    if from_email is None:
        from_email = get_from_email()

    backend = get_email_backend()

    email = EmailMultiAlternatives(
        subject=subject,
        body=message,
        from_email=from_email,
        to=recipient_list,
        connection=backend,
    )

    if html_message:
        email.attach_alternative(html_message, 'text/html')

    return email.send()


def send_password_reset_email(user, token):
    """
    Send password reset email to user.

    Args:
        user: User object
        token: PasswordResetToken object

    Returns:
        Number of emails sent (0 or 1)
    """
    from django.template.loader import render_to_string
    from .url import get_absolute_url

    # Build reset URL
    reset_url = get_absolute_url('reset_password', token.token)

    with translation.override(user_language(user)):
        subject = _('Reset your %(site_name)s password') % {'site_name': settings.SITE_NAME}

        context = {
            'user': user,
            'reset_url': reset_url,
            'site_name': settings.SITE_NAME,
        }

        html_message = render_to_string('emails/password_reset.html', context)
        text_message = render_to_string('emails/password_reset.txt', context)

    return send_email(
        subject=subject,
        message=text_message,
        recipient_list=[user.email],
        html_message=html_message
    )


def send_welcome_email(user, organization, password=None):
    """
    Send welcome email to newly registered user.

    Args:
        user: User object
        organization: Organization object
        password: Optional password to include in email (for admin-created accounts)

    Returns:
        Number of emails sent (0 or 1)
    """
    import random
    from django.template.loader import render_to_string
    from .models import WelcomeEmailFact
    from .url import get_absolute_url

    # Build login URL
    login_url = get_absolute_url('login')

    # Build Dreyfus model URL
    dreyfus_url = get_absolute_url('/landing/dreyfus-model/')

    with translation.override(user_language(user, organization)):
        # Get active facts from database
        active_facts = list(WelcomeEmailFact.objects.filter(is_active=True))

        if active_facts:
            # Select a random fact from the database
            selected_fact_obj = random.choice(active_facts)
            selected_fact = {
                'title': selected_fact_obj.title,
                'content': selected_fact_obj.content
            }
        else:
            # Fallback if no facts in database
            selected_fact = {
                'title': _('The Power of 360 Feedback'),
                'content': _('Research shows that <strong>360-degree feedback increases self-awareness by up to 30%</strong> and significantly improves leadership effectiveness.')
            }

        # Use different templates based on whether password is provided
        if password:
            # Admin-created account with credentials
            subject = _('Welcome to %(site_name)s - Your Account is Ready') % {'site_name': settings.SITE_NAME}
            html_template = 'emails/welcome.html'
            text_template = 'emails/welcome.txt'
        else:
            # Invited member (already set their own password)
            subject = _('Welcome to %(organization)s!') % {'organization': organization.name}
            html_template = 'emails/welcome_member.html'
            text_template = 'emails/welcome_member.txt'

        # Render email templates
        context = {
            'organization': organization,
            'user': user,
            'password': password,
            'login_url': login_url,
            'dreyfus_url': dreyfus_url,
            'site_name': settings.SITE_NAME,
            'fact_title': selected_fact['title'],
            'fact_content': selected_fact['content'],
        }

        html_message = render_to_string(html_template, context)
        text_message = render_to_string(text_template, context)

    return send_email(
        subject=subject,
        message=text_message,
        recipient_list=[user.email],
        html_message=html_message,
        from_email=organization.from_email if organization.from_email else None
    )


def _send_account_notice(email, language, subject, template, context):
    """Render emails/<template>.html and .txt in the recipient's language and send them to one address.

    subject is a lazy text with a %(site_name)s placeholder.
    """
    from django.template.loader import render_to_string
    from django.utils import timezone
    from django.utils.formats import date_format

    with translation.override(language):
        now = timezone.localtime()
        context = {
            'site_name': settings.SITE_NAME,
            'date': date_format(now, 'DATE_FORMAT'),
            'time': date_format(now, 'H:i'),
            **context,
        }
        subject = str(subject) % {'site_name': settings.SITE_NAME}
        html_message = render_to_string(f'emails/{template}.html', context)
        text_message = render_to_string(f'emails/{template}.txt', context)

    return send_email(subject=subject, message=text_message, recipient_list=[email], html_message=html_message)


def send_password_changed_email(user):
    """Security notice after the user's password changed, with a way out if it was not them."""
    from .url import get_absolute_url

    return _send_account_notice(
        user.email, user_language(user), gettext_lazy('Your %(site_name)s password was changed'),
        'password_changed', {'user': user, 'reset_url': get_absolute_url('forgot_password')},
    )


def send_email_changed_email(user, old_email):
    """Security notice to the old address after the user's email address changed."""
    profile = getattr(user, 'profile', None)

    return _send_account_notice(
        old_email, user_language(user),
        gettext_lazy('The email address of your %(site_name)s account was changed'),
        'email_changed', {
            'user': user,
            'old_email': old_email,
            'new_email': user.email,
            'organization': getattr(profile, 'organization', None),
        },
    )
