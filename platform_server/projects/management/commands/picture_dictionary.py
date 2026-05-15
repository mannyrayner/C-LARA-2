from __future__ import annotations

from django.core.exceptions import PermissionDenied
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from projects.models import Community, PictureDictionary, Project
from projects.picture_dictionary import (
    add_words,
    add_words_from_text,
    compile_picture_dictionary,
    ensure_picture_dictionary_for_community,
    import_project_as_picture_dictionary,
    load_text_argument,
    remove_words,
)


class Command(BaseCommand):
    help = "Manage community picture dictionaries (first-cut Phase A tooling)."

    def add_arguments(self, parser):
        parser.add_argument("action", choices=["ensure", "compile", "add", "remove", "add-from-text", "import-project"])
        parser.add_argument("--community-id", type=int, required=True)
        parser.add_argument("--organiser", required=True, help="Username of community organiser")
        parser.add_argument("--words", default="", help="Comma-separated words")
        parser.add_argument("--text", default="", help="Source text for add-from-text")
        parser.add_argument("--text-file", default="", help="UTF-8 file path for add-from-text")
        parser.add_argument("--source-project-id", type=int, help="Community project to import as a dictionary copy")

    def handle(self, *args, **options):
        action = options["action"]
        community = Community.objects.filter(pk=options["community_id"]).first()
        if not community:
            raise CommandError("Unknown community")

        User = get_user_model()
        organiser = User.objects.filter(username=options["organiser"]).first()
        if not organiser:
            raise CommandError("Unknown organiser user")

        if action == "import-project":
            source_project_id = options.get("source_project_id")
            if not source_project_id:
                raise CommandError("import-project requires --source-project-id")
            source_project = Project.objects.filter(pk=source_project_id, community=community).first()
            if not source_project:
                raise CommandError("Unknown source project for this community")
            try:
                dictionary, summary = import_project_as_picture_dictionary(
                    community=community,
                    organiser=organiser,
                    source_project=source_project,
                )
            except (PermissionDenied, ValueError) as exc:
                raise CommandError(str(exc)) from exc
            self.stdout.write(
                self.style.SUCCESS(
                    f"Imported project {source_project.id} as dictionary project {dictionary.project_id}: "
                    f"entries={summary.get('entries_created', 0)}"
                )
            )
            for diagnostic in summary.get("diagnostics", []):
                self.stdout.write(str(diagnostic))
            return

        try:
            dictionary = ensure_picture_dictionary_for_community(community=community, organiser=organiser)
        except PermissionDenied as exc:
            raise CommandError(str(exc)) from exc

        if action == "ensure":
            self.stdout.write(
                self.style.SUCCESS(
                    f"Picture dictionary ready: id={dictionary.id}, project_id={dictionary.project_id}, community={community.name}"
                )
            )
            return

        dictionary = PictureDictionary.objects.select_related("project", "community").get(pk=dictionary.pk)

        if action == "compile":
            result = compile_picture_dictionary(dictionary=dictionary)
            self.stdout.write(
                self.style.SUCCESS(
                    "Compiled dictionary project "
                    f"{dictionary.project_id}: pages={result['pages']}, "
                    f"page_rows_synced={result['page_rows_synced']}, "
                    f"annotation_run={result.get('annotation_run')}, "
                    f"generated_images={result.get('generated_images')}"
                )
            )
            if result.get("image_generation_note"):
                self.stdout.write(result["image_generation_note"])
            return

        words = [part.strip() for part in str(options.get("words") or "").split(",") if part.strip()]

        if action == "add":
            added = add_words(dictionary=dictionary, words=words)
            self.stdout.write(self.style.SUCCESS(f"Added {added} word(s)."))
            return

        if action == "remove":
            removed = remove_words(dictionary=dictionary, words=words)
            self.stdout.write(self.style.SUCCESS(f"Removed {removed} word(s)."))
            return

        text = load_text_argument(text=options.get("text") or "", text_file=options.get("text_file") or "")
        if action == "add-from-text":
            if not text.strip():
                raise CommandError("add-from-text requires --text or --text-file")
            added = add_words_from_text(dictionary=dictionary, text=text)
            self.stdout.write(self.style.SUCCESS(f"Added {added} word(s) from text."))
            return

        raise CommandError(f"Unsupported action: {action}")
