"""
Product reviews for gathering customer testimonials and ratings.
Used for JSON-LD structured data on landing pages.
"""
from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils.translation import gettext_lazy as _
from core.models import TimeStampedModel, Organization
from core.managers import OrganizationManager


class ProductReview(TimeStampedModel):
    """
    Customer reviews of the Blik platform for displaying on landing pages.
    These reviews feed into JSON-LD structured data for SEO.
    """

    STATUS_CHOICES = [
        ('pending', _('Pending Review')),
        ('approved', _('Approved')),
        ('rejected', _('Rejected')),
    ]

    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name='product_reviews',
        help_text=_('Organization this review belongs to'),
        verbose_name=_('organization')
    )

    # Review content
    rating = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        help_text=_('Rating from 1-5 stars'),
        verbose_name=_('rating')
    )
    review_title = models.CharField(
        max_length=200,
        help_text=_('Short title/headline for the review'),
        verbose_name=_('review title')
    )
    review_text = models.TextField(
        help_text=_('Full review text from the customer'),
        verbose_name=_('review text')
    )

    # Reviewer information
    reviewer_name = models.CharField(
        max_length=100,
        help_text=_('Name of the person giving the review'),
        verbose_name=_('reviewer name')
    )
    reviewer_title = models.CharField(
        max_length=150,
        blank=True,
        help_text=_('Job title of the reviewer (e.g., "HR Manager")'),
        verbose_name=_('reviewer title')
    )
    reviewer_company = models.CharField(
        max_length=100,
        blank=True,
        help_text=_('Company/organization the reviewer works for'),
        verbose_name=_('company')
    )
    reviewer_email = models.EmailField(
        help_text=_('Email address of the reviewer (not shown publicly)'),
        verbose_name=_('reviewer email')
    )

    # Verification and status
    verified_customer = models.BooleanField(
        default=False,
        help_text=_('Verified as actual customer/subscriber'),
        verbose_name=_('verified customer')
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending',
        help_text=_('Review approval status'),
        verbose_name=_('status')
    )

    # Publishing
    is_active = models.BooleanField(
        default=True,
        help_text=_('Active reviews can be displayed publicly'),
        verbose_name=_('active')
    )
    featured = models.BooleanField(
        default=False,
        help_text=_('Featured reviews are highlighted on landing pages'),
        verbose_name=_('featured')
    )
    published_date = models.DateField(
        null=True,
        blank=True,
        help_text=_('Date the review was published (shown in JSON-LD)'),
        verbose_name=_('published date')
    )

    # Metadata
    source = models.CharField(
        max_length=100,
        blank=True,
        help_text=_('Where the review came from (e.g., "Email Survey", "G2", "Direct")'),
        verbose_name=_('source')
    )
    notes = models.TextField(
        blank=True,
        help_text=_('Internal notes about this review (not shown publicly)'),
        verbose_name=_('internal notes')
    )

    objects = OrganizationManager()

    class Meta:
        db_table = 'product_reviews'
        ordering = ['-published_date', '-created_at']
        verbose_name = _('Product Review')
        verbose_name_plural = _('Product Reviews')

    def __str__(self):
        return f"{self.reviewer_name} - {self.rating}★ ({self.get_status_display()})"

    @property
    def star_display(self):
        """Return star rating as visual string"""
        return '★' * self.rating + '☆' * (5 - self.rating)

    @property
    def public_name(self):
        """Reviewer name safe for public output. Hides names that are emails."""
        # ponytail: the quick review falls back to username, which is often an email
        if '@' in self.reviewer_name:
            return 'Verified customer'
        return self.reviewer_name

    @property
    def is_published(self):
        """Check if review is approved and active"""
        return self.status == 'approved' and self.is_active
