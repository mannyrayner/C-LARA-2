from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("projects", "0012_project_processing_methods"),
    ]

    operations = [
        migrations.AddField(
            model_name="project",
            name="access_count",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="project",
            name="published_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
