from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("projects", "0016_exerciseset_flashcard_mode"),
    ]

    operations = [
        migrations.AddField(
            model_name="project",
            name="page_image_text_source",
            field=models.CharField(
                choices=[
                    ("segmentation", "Segmented source text"),
                    ("translation", "Concatenated page translations"),
                ],
                default="segmentation",
                max_length=32,
            ),
        ),
    ]
