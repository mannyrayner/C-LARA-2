from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db.models import Q

from projects.metadata import update_project_discovery_metadata
from projects.models import Project


class Command(BaseCommand):
    help = "Admin-only: backfill discovery metadata keywords for all projects where metadata is missing/stale."

    def add_arguments(self, parser):
        parser.add_argument(
            "--admin-username",
            required=True,
            help="Username of an admin/staff user authorizing this maintenance command.",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Regenerate metadata for all projects regardless of staleness.",
        )

    def handle(self, *args, **options):
        username = str(options.get("admin_username") or "").strip()
        force = bool(options.get("force"))
        User = get_user_model()
        admin_user = User.objects.filter(username=username).first()
        if admin_user is None or not (admin_user.is_staff or admin_user.is_superuser):
            raise CommandError("--admin-username must belong to a staff/superuser account")

        qs = Project.objects.order_by("id")
        if not force:
            qs = qs.filter(
                Q(discovery_keywords=[]) |
                Q(discovery_keywords_en=[]) |
                Q(discovery_metadata_updated_at__isnull=True) |
                Q(discovery_word_count=0)
            )

        total = 0
        updated = 0
        for project in qs.iterator():
            total += 1
            if update_project_discovery_metadata(project, force=True):
                updated += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Admin {username} processed {total} project(s); updated {updated}."
            )
        )
