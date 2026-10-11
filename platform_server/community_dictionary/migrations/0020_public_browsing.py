from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('community_dictionary', '0019_batch_descriptions')]

    operations = [
        migrations.AddField(
            model_name='dictionary', name='public_browsing_enabled',
            field=models.BooleanField(default=False)),
        migrations.AddField(
            model_name='dictionary', name='public_browsing_revision',
            field=models.PositiveIntegerField(default=0)),
    ]
