from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("projects", "0026_communityimagevote_communityorganiserreview"),
    ]

    operations = [
        migrations.AddField(
            model_name="project",
            name="discovery_keywords",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name="project",
            name="discovery_level",
            field=models.CharField(blank=True, default="", max_length=16),
        ),
        migrations.AddField(
            model_name="project",
            name="discovery_metadata_updated_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="project",
            name="discovery_summary",
            field=models.TextField(blank=True, default=""),
        ),
        migrations.AddField(
            model_name="project",
            name="discovery_word_count",
            field=models.PositiveIntegerField(default=0),
        ),
    ]
