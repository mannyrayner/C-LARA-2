from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ("projects", "0014_social_features"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="ExerciseSet",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("exercise_type", models.CharField(choices=[("cloze", "Cloze"), ("flashcard", "Flashcard")], default="cloze", max_length=32)),
                ("theme", models.CharField(choices=[("vocabulary", "Vocabulary"), ("grammar", "Grammar"), ("morphology", "Morphology"), ("grammar_morphology", "Grammar/Morphology")], default="vocabulary", max_length=32)),
                ("title", models.CharField(blank=True, max_length=255)),
                ("instructions", models.TextField(blank=True)),
                ("status", models.CharField(choices=[("draft", "Draft"), ("ready", "Ready"), ("published", "Published")], default="draft", max_length=16)),
                ("is_published", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("created_by", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="created_exercise_sets", to=settings.AUTH_USER_MODEL)),
                ("project", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="exercise_sets", to="projects.project")),
            ],
            options={"ordering": ["-updated_at"]},
        ),
        migrations.CreateModel(
            name="ExerciseItem",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("order_index", models.PositiveIntegerField(default=0)),
                ("page_number", models.PositiveIntegerField(default=1)),
                ("segment_index", models.PositiveIntegerField(default=0)),
                ("segment_text", models.TextField(blank=True)),
                ("prompt", models.TextField(blank=True)),
                ("answer", models.CharField(blank=True, max_length=255)),
                ("options", models.JSONField(blank=True, default=list)),
                ("rationale", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("exercise_set", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="items", to="projects.exerciseset")),
            ],
            options={"ordering": ["order_index", "id"]},
        ),
    ]
