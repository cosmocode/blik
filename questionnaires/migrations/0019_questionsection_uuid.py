import uuid

from django.db import migrations, models


def generate_uuids(apps, schema_editor):
    """Give every existing section its own UUID."""

    QuestionSection = apps.get_model('questionnaires', 'QuestionSection')

    for section in QuestionSection.objects.all():
        section.uuid = uuid.uuid4()
        section.save(update_fields=['uuid'])


class Migration(migrations.Migration):

    dependencies = [
        ('questionnaires', '0018_question_descriptions'),
    ]

    operations = [
        # Nullable first: a default on a new column gives every existing row the same value
        migrations.AddField(
            model_name='questionsection',
            name='uuid',
            field=models.UUIDField(default=uuid.uuid4, editable=False, null=True),
        ),
        migrations.RunPython(generate_uuids, reverse_code=migrations.RunPython.noop),
        migrations.AlterField(
            model_name='questionsection',
            name='uuid',
            field=models.UUIDField(default=uuid.uuid4, editable=False, unique=True, verbose_name='UUID'),
        ),
    ]
