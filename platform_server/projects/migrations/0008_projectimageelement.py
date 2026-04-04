from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ("projects", "0007_projectimagestyle_sample_image_fields"),
    ]

    operations = [
        migrations.CreateModel(
            name="ProjectImageElement",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("name", models.CharField(max_length=255)),
                ("element_type", models.CharField(blank=True, default="character", max_length=64)),
                ("page_refs", models.CharField(blank=True, max_length=255)),
                ("why_consistency_matters", models.TextField(blank=True)),
                ("expanded_description", models.TextField(blank=True)),
                ("expanded_prompt", models.TextField(blank=True)),
                ("is_confirmed", models.BooleanField(default=False)),
                ("ai_model", models.CharField(default="gpt-4o", max_length=64)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("proposed", "Proposed"),
                            ("expanded", "Expanded"),
                            ("confirmed", "Confirmed"),
                        ],
                        default="proposed",
                        max_length=32,
                    ),
                ),
                ("created_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "project",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="image_elements",
                        to="projects.project",
                    ),
                ),
            ],
            options={
                "ordering": ["name", "id"],
                "unique_together": {("project", "name")},
            },
        ),
    ]
