from django.db import migrations


def anonymize_email_names(apps, schema_editor):
    """The quick review stored the username, often an email, as the name."""
    ProductReview = apps.get_model('productreviews', 'ProductReview')
    ProductReview.objects.filter(reviewer_name__contains='@').update(
        reviewer_name='Verified customer')


class Migration(migrations.Migration):

    dependencies = [
        ('productreviews', '0001_initial'),
    ]

    operations = [
        # The email stays in reviewer_email, so reversing has nothing to restore.
        migrations.RunPython(anonymize_email_names, migrations.RunPython.noop),
    ]
