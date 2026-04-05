import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


def ensure_model_table_and_columns(apps, schema_editor, model_name):
    model = apps.get_model("projects", model_name)
    table_name = model._meta.db_table
    table_names = schema_editor.connection.introspection.table_names()
    if table_name not in table_names:
        schema_editor.create_model(model)
        return

    with schema_editor.connection.cursor() as cursor:
        existing_columns = {
            col.name
            for col in schema_editor.connection.introspection.get_table_description(cursor, table_name)
        }

    for field in model._meta.local_fields:
        if field.column not in existing_columns:
            schema_editor.add_field(model, field)


def ensure_compat_schema(apps, schema_editor):
    for name in ("ProjectImageStyle", "ContentComment", "ContentRating"):
        ensure_model_table_and_columns(apps, schema_editor, name)


class Migration(migrations.Migration):

    dependencies = [
        ("projects", "0011_project_access_count_compat"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.CreateModel(
                    name="ContentComment",
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
                        ("text", models.TextField()),
                        ("is_hidden", models.BooleanField(default=False)),
                        ("created_at", models.DateTimeField(default=django.utils.timezone.now)),
                        ("updated_at", models.DateTimeField(auto_now=True)),
                        (
                            "author",
                            models.ForeignKey(
                                on_delete=django.db.models.deletion.CASCADE,
                                related_name="content_comments",
                                to=settings.AUTH_USER_MODEL,
                            ),
                        ),
                        (
                            "project",
                            models.ForeignKey(
                                on_delete=django.db.models.deletion.CASCADE,
                                related_name="content_comments",
                                to="projects.project",
                            ),
                        ),
                    ],
                    options={"ordering": ["project_id", "-created_at"]},
                ),
                migrations.CreateModel(
                    name="ContentRating",
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
                        ("rating", models.IntegerField(default=0)),
                        ("created_at", models.DateTimeField(default=django.utils.timezone.now)),
                        ("updated_at", models.DateTimeField(auto_now=True)),
                        (
                            "project",
                            models.ForeignKey(
                                on_delete=django.db.models.deletion.CASCADE,
                                related_name="content_ratings",
                                to="projects.project",
                            ),
                        ),
                        (
                            "user",
                            models.ForeignKey(
                                on_delete=django.db.models.deletion.CASCADE,
                                related_name="content_ratings",
                                to=settings.AUTH_USER_MODEL,
                            ),
                        ),
                    ],
                    options={"ordering": ["project_id", "user_id"], "unique_together": {("project", "user")}},
                ),
            ],
            database_operations=[
                migrations.RunPython(ensure_compat_schema, migrations.RunPython.noop),
            ],
        )
    ]
