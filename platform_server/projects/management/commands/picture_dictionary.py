from __future__ import annotations

from django.core.exceptions import PermissionDenied
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from projects.models import Community, PictureDictionary
from projects.picture_dictionary import (
    add_words,
    add_words_from_text,
    compile_picture_dictionary,
    ensure_picture_dictionary_for_community,
    load_text_argument,
    remove_words,
)


class Command(BaseCommand):
    help = "Manage community picture dictionaries (first-cut Phase A tooling)."

    def add_arguments(self, parser):
        parser.add_argument("action", choices=["ensure", "compile", "add", "remove", "add-from-text"])
        parser.add_argument("--community-id", type=int, required=True)
        parser.add_argument("--organiser", required=True, help="Username of community organiser")
        parser.add_argument("--words", default="", help="Comma-separated words")
        parser.add_argument("--text", default="", help="Source text for add-from-text")
        parser.add_argument("--text-file", default="", help="UTF-8 file path for add-from-text")

    def handle(self, *args, **options):
        action = options["action"]
        community = Community.objects.filter(pk=options["community_id"]).first()
        if not community:
            raise CommandError("Unknown community")

        User = get_user_model()
        organiser = User.objects.filter(username=options["organiser"]).first()
        if not organiser:
            raise CommandError("Unknown organiser user")

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
                    f"Compiled dictionary project {dictionary.project_id}: pages={result['pages']}, page_rows_synced={result['page_rows_synced']}"
                )
            )
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
