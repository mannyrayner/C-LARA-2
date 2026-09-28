from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from community_dictionary.models import AudioStudy, PhotoStudy
from community_dictionary.storage import delete_file


class Command(BaseCommand):
    help = 'Delete expired private photo/audio drafts (run daily). Saved dictionary media is separate.'

    def handle(self, **options):
        self.expire(PhotoStudy, 'photo')
        self.expire(AudioStudy, 'audio')

    def expire(self, model, name):
        count = 0
        for pk in model.objects.filter(expires_at__lte=timezone.now()).values_list('pk', flat=True).iterator():
            with transaction.atomic():
                study = model.objects.select_for_update().filter(pk=pk, expires_at__lte=timezone.now()).first()
                if study:
                    # Delete file first: a failed unlink must leave a row for the next run.
                    if study.file_path:
                        delete_file(study.file_path)
                    study.delete()
                    count += 1
        self.stdout.write(f'Expired {name} studies removed: {count}')
