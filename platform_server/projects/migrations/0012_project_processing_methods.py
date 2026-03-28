from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("projects", "0011_project_page_image_placement"),
    ]

    operations = [
        migrations.AddField(
            model_name="project",
            name="romanization_method",
            field=models.CharField(default="auto", max_length=32),
        ),
        migrations.AddField(
            model_name="project",
            name="segmentation_method",
            field=models.CharField(default="auto", max_length=32),
        ),
    ]
