from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0008_add_auto_send_report_email'),
    ]

    operations = [
        migrations.CreateModel(
            name='UpgradeStep',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=255, unique=True, verbose_name='name')),
                ('applied_at', models.DateTimeField(auto_now_add=True, verbose_name='applied at')),
                ('success', models.BooleanField(default=False, verbose_name='success')),
                ('error', models.TextField(blank=True, default='', verbose_name='error')),
            ],
            options={
                'db_table': 'upgrade_steps',
                'verbose_name': 'upgrade step',
                'verbose_name_plural': 'upgrade steps',
            },
        ),
    ]
