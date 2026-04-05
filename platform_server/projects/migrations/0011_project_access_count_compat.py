from django.db import migrations, models


def ensure_project_access_count(apps, schema_editor):
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

    if "access_count" not in existing_columns:
        field = project_model._meta.get_field("access_count")
        schema_editor.add_field(project_model, field)


class Migration(migrations.Migration):

    dependencies = [
        ("projects", "0010_project_published_at_compat"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AddField(
                    model_name="project",
                    name="access_count",
                    field=models.PositiveIntegerField(default=0),
                ),
            ],
            database_operations=[
                migrations.RunPython(ensure_project_access_count, migrations.RunPython.noop),
            ],
        ),
    ]
