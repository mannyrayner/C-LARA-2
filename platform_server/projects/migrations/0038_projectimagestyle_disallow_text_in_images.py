from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("projects", "0037_project_audio_mode"),
    ]

    operations = [
        migrations.AddField(
            model_name="projectimagestyle",
            name="disallow_text_in_images",
            field=models.BooleanField(default=False),
        ),
    ]
