from django.db import migrations, models
import django.db.models.deletion
from django.conf import settings
import django.utils.timezone


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Project",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("title", models.CharField(max_length=200)),
                ("description", models.TextField(blank=True)),
                ("source_text", models.TextField()),
                ("language", models.CharField(default="en", max_length=16)),
                ("target_language", models.CharField(default="fr", max_length=16)),
                ("compiled_path", models.CharField(blank=True, max_length=512)),
                ("artifact_root", models.CharField(blank=True, max_length=512)),
                ("is_published", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "owner",
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="projects", to=settings.AUTH_USER_MODEL),
                ),
            ],
            options={
                "ordering": ["-updated_at"],
                "unique_together": {("owner", "title")},
            },
        ),
    ]
