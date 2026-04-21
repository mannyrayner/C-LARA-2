from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("projects", "0029_project_discovery_keywords_en"),
    ]

    operations = [
        migrations.AddField(
            model_name="profile",
            name="dialogue_memory",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddField(
            model_name="profile",
            name="dialogue_memory_enabled",
            field=models.BooleanField(default=True),
        ),
    ]
