from django.db import migrations, models


def ensure_project_published_at(apps, schema_editor):
    project_model = apps.get_model("projects", "Project")
    table_name = project_model._meta.db_table
    table_names = schema_editor.connection.introspection.table_names()
    if table_name not in table_names:
        return

    with schema_editor.connection.cursor() as cursor:
        existing_columns = {
            col.name
            for col in schema_editor.connection.introspection.get_table_description(cursor, table_name)
        }

    if "published_at" not in existing_columns:
        field = project_model._meta.get_field("published_at")
        schema_editor.add_field(project_model, field)


class Migration(migrations.Migration):

    dependencies = [
        ("projects", "0009_ensure_profile_columns"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AddField(
                    model_name="project",
                    name="published_at",
                    field=models.DateTimeField(blank=True, null=True),
                ),
            ],
            database_operations=[
                migrations.RunPython(ensure_project_published_at, migrations.RunPython.noop),
            ],
        ),
    ]
