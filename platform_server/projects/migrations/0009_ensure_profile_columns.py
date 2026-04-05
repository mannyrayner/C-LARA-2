from django.db import migrations


def ensure_profile_columns(apps, schema_editor):
    profile_model = apps.get_model("projects", "Profile")
    table_name = profile_model._meta.db_table
    table_names = schema_editor.connection.introspection.table_names()
    if table_name not in table_names:
        schema_editor.create_model(profile_model)
        return

    with schema_editor.connection.cursor() as cursor:
        existing_columns = {
            col.name
            for col in schema_editor.connection.introspection.get_table_description(cursor, table_name)
        }

    for field in profile_model._meta.local_fields:
        if field.column not in existing_columns:
            schema_editor.add_field(profile_model, field)


class Migration(migrations.Migration):

    dependencies = [
        ("projects", "0008_projectimagepage_generation_prompt_and_more"),
    ]

    operations = [
        migrations.RunPython(ensure_profile_columns, migrations.RunPython.noop),
    ]
