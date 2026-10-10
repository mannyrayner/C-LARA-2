from django.db import migrations, models
import django.utils.timezone


class Migration(migrations.Migration):
    dependencies = [('projects', '0043_legacyprojectimport')]
    operations = [migrations.CreateModel(
        name='PasswordResetLimit',
        fields=[
            ('key', models.CharField(max_length=64, primary_key=True, serialize=False)),
            ('count', models.PositiveIntegerField(default=0)),
            ('window_start', models.DateTimeField(db_index=True, default=django.utils.timezone.now)),
        ],
    )]
