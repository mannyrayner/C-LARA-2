from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("projects", "0027_project_discovery_metadata_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="profile",
            name="dialogue_language",
            field=models.CharField(default="en", max_length=16),
        ),
    ]
