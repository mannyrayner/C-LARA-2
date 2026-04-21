from django.core.management.base import BaseCommand

from projects.metadata import update_project_discovery_metadata
from projects.models import Project


class Command(BaseCommand):
    help = "Generate discovery metadata for published projects that are missing it."

    def add_arguments(self, parser):
        parser.add_argument(
            "--force",
            action="store_true",
            help="Regenerate metadata for all published projects, not only missing ones.",
        )

    def handle(self, *args, **options):
        force = bool(options.get("force"))
        qs = Project.objects.filter(is_published=True).order_by("id")
        if not force:
            qs = qs.filter(discovery_summary="")
        total = 0
        updated = 0
        for project in qs.iterator():
            total += 1
            if update_project_discovery_metadata(project, force=force):
                updated += 1
        self.stdout.write(self.style.SUCCESS(f"Processed {total} published project(s); updated {updated}."))
