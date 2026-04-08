from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('projects', '0015_exerciseset_exerciseitem'),
    ]

    operations = [
        migrations.AddField(
            model_name='exerciseset',
            name='flashcard_mode',
            field=models.CharField(blank=True, choices=[('form_to_meaning', 'Form → meaning'), ('meaning_to_form', 'Meaning → form')], default='', max_length=32),
        ),
    ]
