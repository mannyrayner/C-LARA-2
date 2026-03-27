from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ("projects", "0005_project_ai_model"),
    ]

    operations = [
        migrations.CreateModel(
            name="ProjectImageStyle",
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
                ("style_brief", models.TextField(blank=True)),
                ("expanded_style_description", models.TextField(blank=True)),
                ("representative_excerpt", models.TextField(blank=True)),
                ("sample_image_prompt", models.TextField(blank=True)),
                ("ai_model", models.CharField(default="gpt-4o", max_length=64)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("draft", "Draft"),
                            ("generated", "Generated"),
                            ("approved", "Approved"),
                        ],
                        default="draft",
                        max_length=32,
                    ),
                ),
                ("created_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "project",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="image_style",
                        to="projects.project",
                    ),
                ),
            ],
            options={
                "ordering": ["-updated_at"],
            },
        ),
    ]
