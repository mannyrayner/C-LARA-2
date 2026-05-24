from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("projects", "0035_issueupdatesuggestion"),
    ]

    operations = [
        migrations.AddField(
            model_name="profile",
            name="use_personal_openai_key",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="profile",
            name="openai_api_key",
            field=models.CharField(blank=True, default="", max_length=255),
        ),
    ]
