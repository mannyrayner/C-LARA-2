from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("projects", "0004_taskupdate"),
    ]

    operations = [
        migrations.AddField(
            model_name="project",
            name="ai_model",
            field=models.CharField(default="gpt-4o", max_length=64),
        ),
    ]
