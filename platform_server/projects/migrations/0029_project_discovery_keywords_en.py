from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("projects", "0028_profile_dialogue_language"),
    ]

    operations = [
        migrations.AddField(
            model_name="project",
            name="discovery_keywords_en",
            field=models.JSONField(blank=True, default=list),
        ),
    ]
