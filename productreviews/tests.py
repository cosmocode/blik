from django.test import TestCase
from importlib import import_module

from django.apps import apps
from django.contrib.auth.models import User
from django.urls import reverse

from accounts.models import UserProfile
from core.models import Organization
from .models import ProductReview


class PublicNameTests(TestCase):
    def test_email_is_hidden(self):
        review = ProductReview(reviewer_name='someone@example.com', reviewer_email='someone@example.com')
        self.assertEqual(review.public_name, 'Verified customer')

    def test_plain_name_is_kept(self):
        review = ProductReview(reviewer_name='Jane Doe', reviewer_email='jane@example.com')
        self.assertEqual(review.public_name, 'Jane Doe')


def make_review(org, name):
    return ProductReview.objects.create(
        organization=org, rating=5, review_title='Great', review_text='Great.',
        reviewer_name=name, reviewer_email='someone@example.com')


class StoredNameTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name='Acme', email='org@acme.example')

    def test_migration_replaces_email_names(self):
        email_review = make_review(self.org, 'someone@example.com')
        plain_review = make_review(self.org, 'Jane Doe')

        migration = import_module('productreviews.migrations.0002_anonymize_email_reviewer_names')
        migration.anonymize_email_names(apps, None)

        email_review.refresh_from_db()
        plain_review.refresh_from_db()
        self.assertEqual(email_review.reviewer_name, 'Verified customer')
        self.assertEqual(email_review.reviewer_email, 'someone@example.com')
        self.assertEqual(plain_review.reviewer_name, 'Jane Doe')

    def test_quick_review_does_not_store_an_email_as_name(self):
        user = User.objects.create_user(
            username='jane@acme.example', email='jane@acme.example', password='pw')
        UserProfile.objects.create(user=user, organization=self.org)

        self.client.force_login(user)
        self.client.post(reverse('quick_product_review'), {'rating': '5'})

        review = ProductReview.objects.get(reviewer_email='jane@acme.example')
        self.assertEqual(review.reviewer_name, 'Verified customer')
