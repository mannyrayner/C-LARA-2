from __future__ import annotations

import time

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Stub Django Q cluster runner for development environments."

    def handle(self, *args, **options):
        self.stdout.write(
            self.style.NOTICE(
                "Starting django_q stub qcluster. Background tasks run inline or via threads; "
                "leave this process running to mimic the real service."
            )
        )
        try:
            while True:
                time.sleep(60)
        except KeyboardInterrupt:
            self.stdout.write(self.style.NOTICE("Stopping django_q stub qcluster."))
