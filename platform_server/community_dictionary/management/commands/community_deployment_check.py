import json
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from core import deployment_activity


class Command(BaseCommand):
    help = 'Read-only deployment preflight. No migrations, API calls or content changes.'

    def add_arguments(self, parser):
        parser.add_argument('--activity-dir', required=True)
        parser.add_argument('--backend', choices=['sqlite', 'postgresql'], required=True)

    def handle(self, *args, **options):
        configured = deployment_activity.directory()
        if configured is None or configured.resolve() != Path(options['activity_dir']).resolve():
            raise CommandError('Deployment activity directory does not match the controller.')
        if not configured.is_dir():
            raise CommandError('Deployment activity directory has not been installed.')
        # A disposable lease checks actual service-user write permission. It
        # never reads or changes dictionary contents.
        with deployment_activity.activity('deployment-preflight', respect_gate=False):
            pass
        if connection.vendor != options['backend']:
            raise CommandError('Unexpected database backend.')
        if settings.USE_REAL_DJANGO_Q:
            raise CommandError('This initial drain protocol supports the bounded local queue only; do not switch queues to bypass this check.')
        import django_q.tasks
        if getattr(django_q.tasks, 'DEPLOYMENT_ACTIVITY_VERSION', None) != deployment_activity.VERSION:
            raise CommandError('The running queue adapter does not support deployment draining.')
        executor = MigrationExecutor(connection)
        if executor.migration_plan(executor.loader.graph.leaf_nodes()):
            raise CommandError('Pending migrations require a separately reviewed deployment.')
        self.stdout.write(json.dumps({'ready': True, 'backend': connection.vendor,
                                      'activity_version': deployment_activity.VERSION}))
