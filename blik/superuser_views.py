"""
Superuser-only views for administrative tasks
"""
from datetime import timedelta
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.contrib.auth.models import User
from django.db import transaction
from django.utils.translation import gettext as _

from core.models import Organization
from accounts.models import UserProfile
from core.email import send_welcome_email
from accounts.permissions import assign_organization_admin
from accounts.services import create_user_with_email_as_username


@login_required
def create_organization(request):
    """
    Superuser-only page to create organizations without payment plans.

    Creates the organization and sends an invitation to the specified admin email.
    The invited admin goes through the normal invitation acceptance flow.
    """
    if not request.user.is_superuser:
        messages.error(request, _('You do not have permission to create organizations.'))
        return redirect('admin_dashboard')

    if request.method == 'POST':
        org_name = request.POST.get('org_name', '').strip()
        admin_email = request.POST.get('admin_email', '').strip().lower()

        # Validation
        if not org_name:
            messages.error(request, _('Organization name is required.'))
            return render(request, 'superuser/create_organization.html')

        if not admin_email:
            messages.error(request, _('Admin email is required.'))
            return render(request, 'superuser/create_organization.html')

        # Check if organization with this name already exists
        if Organization.objects.filter(name=org_name).exists():
            messages.error(request, _('Organization "%(name)s" already exists.') % {'name': org_name})
            return render(request, 'superuser/create_organization.html')

        # Check if user with this email already exists
        existing_user = User.objects.filter(email=admin_email).first()
        if existing_user:
            # Check if user already has a profile/organization
            if hasattr(existing_user, 'profile') and existing_user.profile.organization:
                messages.error(
                    request,
                    _('User with email %(email)s already belongs to organization: %(organization)s')
                    % {'email': admin_email, 'organization': existing_user.profile.organization.name}
                )
                return render(request, 'superuser/create_organization.html')

        try:
            with transaction.atomic():
                # Create organization
                org = Organization.objects.create(
                    name=org_name,
                    email=admin_email,
                    is_active=True,
                    allow_registration=False,
                    default_users_can_create_cycles=False
                )

                # Create user account with centralized function
                try:
                    user, password = create_user_with_email_as_username(
                        email=admin_email,
                        password=None  # Generate random password
                    )
                except ValueError as e:
                    messages.error(request, _('Failed to create user: %(error)s') % {'error': e})
                    return redirect('superuser_create_organization')

                # Create user profile with admin privileges
                UserProfile.objects.create(
                    user=user,
                    organization=org,
                    can_create_cycles_for_others=True  # Admins can create cycles for others
                )

                # Assign organization admin permissions
                assign_organization_admin(user)

                # Send welcome email with credentials
                try:
                    send_welcome_email(user, org, password=password)
                    messages.success(
                        request,
                        _('Organization "%(name)s" created successfully. Login credentials sent to %(email)s.')
                        % {'name': org_name, 'email': admin_email}
                    )
                    return redirect('superuser_create_organization')
                except Exception as e:
                    # Rollback will happen automatically due to transaction.atomic()
                    raise Exception(_('Failed to send welcome email: %(error)s') % {'error': e})

        except Exception as e:
            messages.error(request, _('Failed to create organization: %(error)s') % {'error': e})
            return render(request, 'superuser/create_organization.html')

    # GET request - show form
    # Get recent organizations for reference
    recent_orgs = Organization.objects.order_by('-created_at')[:10]

    return render(request, 'superuser/create_organization.html', {
        'recent_orgs': recent_orgs
    })
