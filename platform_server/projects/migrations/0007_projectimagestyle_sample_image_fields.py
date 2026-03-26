from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("projects", "0006_projectimagestyle"),
    ]

    operations = [
        migrations.AddField(
            model_name="projectimagestyle",
            name="sample_image_model",
            field=models.CharField(default="gpt-image-1", max_length=64),
        ),
        migrations.AddField(
            model_name="projectimagestyle",
            name="sample_image_path",
            field=models.CharField(blank=True, max_length=512),
        ),
        migrations.AddField(
            model_name="projectimagestyle",
            name="sample_image_revised_prompt",
            field=models.TextField(blank=True),
        ),
    ]
