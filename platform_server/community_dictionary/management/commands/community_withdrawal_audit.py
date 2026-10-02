"""Read-only preflight, usable before the new participation tables are installed."""
from django.core.management.base import BaseCommand, CommandError
from community_dictionary.models import Contribution


class Command(BaseCommand):
    help = 'Count legacy private contributions before the one-time restoration migration.'

    def add_arguments(self, parser):
        parser.add_argument('--expect-empty', action='store_true', help='Fail if private content would be restored (recommended on AWS).')

    def handle(self, *args, **options):
        private = Contribution.objects.filter(entry__dictionary__personal=True).exclude(status='removed')
        count = private.count()
        self.stdout.write(f'Private contributions: {count}')
        self.stdout.write(f'Private entries: {private.values("entry_id").distinct().count()}')
        self.stdout.write('No content, files or participation states were changed.')
        if options['expect_empty'] and count:
            raise CommandError('Private content exists. Do not run migration 0009 on this database until its restoration has been reviewed.')
