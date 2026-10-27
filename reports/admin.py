from django.contrib import admin
from django.utils.html import format_html
from django.utils import timezone
from django.utils.translation import gettext as _, gettext_lazy
from .models import Report


@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    list_display = ['cycle', 'available', 'generated_at', 'access_count', 'last_accessed', 'token_status']
    list_filter = ['available', 'generated_at', 'last_accessed']
    search_fields = ['cycle__reviewee__name', 'access_token']
    list_select_related = ['cycle', 'cycle__reviewee']
    readonly_fields = ['cycle', 'generated_at', 'created_at', 'updated_at', 'access_token', 'last_accessed', 'access_count', 'token_expiry_status']

    def token_status(self, obj):
        """Display token expiration status with color coding"""
        if not obj.access_token_expires:
            return format_html('<span style="color: gray;">{}</span>', _('No expiry'))

        if obj.access_token_expired:
            return format_html('<span style="color: red; font-weight: bold;">{}</span>', _('Expired'))

        time_left = obj.access_token_expires - timezone.now()
        if time_left.days < 7:
            return format_html('<span style="color: orange;">{}</span>', _('Expires in %(days)s days') % {'days': time_left.days})

        return format_html('<span style="color: green;">{}</span>', _('Valid (%(days)s days)') % {'days': time_left.days})

    token_status.short_description = gettext_lazy('Token Status')

    def token_expiry_status(self, obj):
        """Detailed token expiration info for detail view"""
        if not obj.access_token_expires:
            return _('No expiration set')

        if obj.access_token_expired:
            return format_html('<span style="color: red; font-weight: bold;">{}</span>',
                             _('EXPIRED on %(date)s') % {'date': obj.access_token_expires.strftime('%Y-%m-%d %H:%M')})

        time_left = obj.access_token_expires - timezone.now()
        return format_html('<span style="color: green;">{}</span>',
                         _('Expires on %(date)s (%(days)s days, %(hours)s hours remaining)') % {
                             'date': obj.access_token_expires.strftime('%Y-%m-%d %H:%M'),
                             'days': time_left.days,
                             'hours': time_left.seconds // 3600})

    token_expiry_status.short_description = gettext_lazy('Token Expiration')
