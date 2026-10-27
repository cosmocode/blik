"""
Django admin configuration for API models.
"""
from django.contrib import admin
from django.utils.translation import gettext_lazy as _
from .models import APIToken, WebhookEndpoint, WebhookDelivery


@admin.register(APIToken)
class APITokenAdmin(admin.ModelAdmin):
    """Admin interface for API tokens."""

    list_display = [
        "name",
        "organization",
        "created_by",
        "is_active",
        "expires_at",
        "last_used_at",
        "rate_limit",
    ]
    list_filter = ["is_active", "organization", "created_at"]
    search_fields = ["name", "organization__name"]
    readonly_fields = ["token", "created_at", "updated_at", "last_used_at"]

    fieldsets = (
        (_("Basic Info"), {"fields": ("organization", "created_by", "name", "is_active")}),
        (_("Token"), {"fields": ("token", "expires_at")}),
        (_("Permissions"), {"fields": ("permissions", "rate_limit")}),
        (
            _("Stats"),
            {"fields": ("last_used_at", "created_at", "updated_at"), "classes": ("collapse",)},
        ),
    )

    def get_readonly_fields(self, request, obj=None):
        """Make token read-only after creation."""
        if obj:  # Editing
            return self.readonly_fields + ["organization", "created_by"]
        return self.readonly_fields


@admin.register(WebhookEndpoint)
class WebhookEndpointAdmin(admin.ModelAdmin):
    """Admin interface for webhook endpoints."""

    list_display = [
        "name",
        "organization",
        "url",
        "is_active",
        "success_count",
        "failure_count",
        "last_triggered_at",
    ]
    list_filter = ["is_active", "organization", "created_at"]
    search_fields = ["name", "organization__name", "url"]
    readonly_fields = [
        "secret",
        "success_count",
        "failure_count",
        "last_triggered_at",
        "created_at",
        "updated_at",
    ]

    fieldsets = (
        (_("Basic Info"), {"fields": ("organization", "created_by", "name", "url", "is_active")}),
        (_("Events"), {"fields": ("events",)}),
        (_("Security"), {"fields": ("secret",)}),
        (
            _("Stats"),
            {
                "fields": (
                    "success_count",
                    "failure_count",
                    "last_triggered_at",
                    "created_at",
                    "updated_at",
                ),
                "classes": ("collapse",),
            },
        ),
    )

    def get_readonly_fields(self, request, obj=None):
        """Make organization and secret read-only after creation."""
        if obj:  # Editing
            return self.readonly_fields + ["organization", "created_by"]
        return self.readonly_fields


@admin.register(WebhookDelivery)
class WebhookDeliveryAdmin(admin.ModelAdmin):
    """Admin interface for webhook delivery logs."""

    list_display = [
        "id",
        "endpoint",
        "event_type",
        "status_code",
        "attempt_count",
        "is_successful",
        "created_at",
        "delivered_at",
    ]
    list_filter = ["event_type", "status_code", "created_at"]
    search_fields = ["event_type", "endpoint__name", "endpoint__url"]
    readonly_fields = [
        "endpoint",
        "event_type",
        "payload",
        "created_at",
        "delivered_at",
        "status_code",
        "response_body",
        "error_message",
        "attempt_count",
    ]

    fieldsets = (
        (_("Delivery Info"), {"fields": ("endpoint", "event_type", "created_at")}),
        (_("Payload"), {"fields": ("payload",), "classes": ("collapse",)}),
        (
            _("Response"),
            {
                "fields": (
                    "delivered_at",
                    "status_code",
                    "response_body",
                    "error_message",
                    "attempt_count",
                )
            },
        ),
    )

    def has_add_permission(self, request):
        """Disable manual creation of delivery logs."""
        return False

    def has_change_permission(self, request, obj=None):
        """Make delivery logs read-only."""
        return False

    def is_successful(self, obj):
        """Display success status."""
        return obj.is_successful

    is_successful.boolean = True
    is_successful.short_description = _("Success")
