from django.core.management.base import BaseCommand
from community_dictionary.models import PortRun
from community_dictionary.port_tasks import resume


class Command(BaseCommand):
    help = 'Resume queued language-port work; abandon attempts interrupted for 15 minutes without repeating paid calls.'

    def handle(self,*args,**options):
        count = 0
        for run in PortRun.objects.filter(status__in=['running','cancelled'],settled=False).select_related('port__user'):
            resume(run.port.user,run.pk)
            count += 1
        self.stdout.write(f'Checked {count} unfinished language ports. No provider requests were replayed.')
