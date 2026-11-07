"""Add a co-owner role to the existing membership column; no schema/data SQL."""
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('community_dictionary', '0028_word_audio_settings')]

    operations = [
        migrations.AlterField(
            model_name='membership',
            name='role',
            field=models.CharField(max_length=12, default='member', choices=[
                ('member', 'Member'), ('editor', 'Editor'),
                ('coordinator', 'Coordinator'), ('co_owner', 'Co-owner'),
            ]),
        ),
    ]
