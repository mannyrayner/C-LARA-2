import json
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from pipeline.stage_artifacts import read_stage_artifact, write_stage_artifact

from projects.models import Community, CommunityMembership, PictureDictionary, PictureDictionaryEntry, Project, ProjectImagePage
from projects.picture_dictionary import _manual_rows_from_entries
from projects.views import _build_picture_glosses_for_compile


class PictureDictionaryCommandTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.organiser = User.objects.create_user(username="dictorg", password="pw")
        self.member = User.objects.create_user(username="dictmember", password="pw")
        self.community = Community.objects.create(name="German Community", language="de")
        CommunityMembership.objects.create(
            community=self.community,
            user=self.organiser,
            role=CommunityMembership.ROLE_ORGANISER,
        )
        CommunityMembership.objects.create(
            community=self.community,
            user=self.member,
            role=CommunityMembership.ROLE_MEMBER,
        )

    def test_ensure_add_remove_and_compile_picture_dictionary(self):
        call_command(
            "picture_dictionary",
            "ensure",
            community_id=self.community.id,
            organiser=self.organiser.username,
        )
        dictionary = PictureDictionary.objects.get(community=self.community)
        self.assertEqual(dictionary.project.community_id, self.community.id)
        self.assertEqual(dictionary.project.language, "de")

        call_command(
            "picture_dictionary",
            "add",
            community_id=self.community.id,
            organiser=self.organiser.username,
            words="Pinguin, Oper, Pinguin",
        )
        dictionary.refresh_from_db()
        self.assertEqual(dictionary.project.source_text, "Pinguin\nOper")

        call_command(
            "picture_dictionary",
            "remove",
            community_id=self.community.id,
            organiser=self.organiser.username,
            words="Oper",
        )
        dictionary.refresh_from_db()
        self.assertIn("Pinguin", dictionary.project.source_text)
        self.assertNotIn("Oper", dictionary.project.source_text)

        call_command(
            "picture_dictionary",
            "add-from-text",
            community_id=self.community.id,
            organiser=self.organiser.username,
            text="Frida ist ein Pinguin in der Antarktis.",
        )
        dictionary.refresh_from_db()
        self.assertIn("Frida", dictionary.project.source_text)

        call_command(
            "picture_dictionary",
            "compile",
            community_id=self.community.id,
            organiser=self.organiser.username,
        )
        self.assertEqual(dictionary.project.image_pages.count(), 6)
        seg1_path = dictionary.project.artifact_dir() / "runs" / "run_picture_dictionary" / "stages" / "segmentation_phase_1.json"
        self.assertTrue(seg1_path.exists())
        payload = seg1_path.read_text(encoding="utf-8")
        self.assertIn('"source": "picture_dictionary"', payload)
        for stage_name in ("segmentation_phase_2", "mwe", "lemma", "gloss", "romanization", "pinyin"):
            stage_path = dictionary.project.artifact_dir() / "runs" / "run_picture_dictionary" / "stages" / f"{stage_name}.json"
            self.assertTrue(stage_path.exists())

    def test_add_words_refreshes_placeholder_stage_artifacts_for_manual_editor(self):
        call_command(
            "picture_dictionary",
            "ensure",
            community_id=self.community.id,
            organiser=self.organiser.username,
        )
        dictionary = PictureDictionary.objects.get(community=self.community)
        call_command(
            "picture_dictionary",
            "add",
            community_id=self.community.id,
            organiser=self.organiser.username,
            words="Kuma, Nori",
        )
        run_dir = dictionary.project.artifact_dir() / "runs" / "run_picture_dictionary"
        seg2 = read_stage_artifact(run_dir, "segmentation_phase_2")
        self.assertEqual([p.get("surface") for p in seg2.get("pages", [])], ["Kuma", "Nori"])
        for stage_name in ("translation", "mwe", "lemma", "gloss", "pinyin"):
            stage_path = run_dir / "stages" / f"{stage_name}.json"
            self.assertTrue(stage_path.exists())

    def test_placeholder_refresh_preserves_existing_annotations(self):
        call_command("picture_dictionary", "ensure", community_id=self.community.id, organiser=self.organiser.username)
        dictionary = PictureDictionary.objects.get(community=self.community)
        call_command("picture_dictionary", "add", community_id=self.community.id, organiser=self.organiser.username, words="Katze")
        run_dir = dictionary.project.artifact_dir() / "runs" / "run_picture_dictionary"
        gloss_payload = read_stage_artifact(run_dir, "gloss")
        gloss_payload["pages"][0]["segments"][0]["tokens"][0]["annotations"] = {"lemma": "Katze", "pos": "NOUN", "gloss": "cat"}
        write_stage_artifact(run_dir, "gloss", gloss_payload)
        call_command("picture_dictionary", "add", community_id=self.community.id, organiser=self.organiser.username, words="Hund")
        gloss_after = read_stage_artifact(run_dir, "gloss")
        tokens = [p["segments"][0]["tokens"][0] for p in gloss_after.get("pages", [])]
        by_surface = {t["surface"]: t for t in tokens}
        self.assertEqual(by_surface["Katze"]["annotations"].get("gloss"), "cat")
        self.assertEqual(by_surface["Hund"].get("annotations", {}), {})

    def test_removing_word_removes_corresponding_dictionary_page(self):
        call_command("picture_dictionary", "ensure", community_id=self.community.id, organiser=self.organiser.username)
        dictionary = PictureDictionary.objects.get(community=self.community)
        call_command(
            "picture_dictionary",
            "add",
            community_id=self.community.id,
            organiser=self.organiser.username,
            words="Katze, Hund",
        )
        self.assertEqual(dictionary.project.image_pages.count(), 2)
        call_command(
            "picture_dictionary",
            "remove",
            community_id=self.community.id,
            organiser=self.organiser.username,
            words="Hund",
        )
        pages = list(dictionary.project.image_pages.order_by("page_number"))
        self.assertEqual(len(pages), 1)
        self.assertEqual(pages[0].page_text, "Katze")
        seg2 = read_stage_artifact(dictionary.project.artifact_dir() / "runs" / "run_picture_dictionary", "segmentation_phase_2")
        self.assertEqual([p.get("surface") for p in seg2.get("pages", [])], ["Katze"])

    def test_compile_uses_translation_text_for_page_prompts_when_configured(self):
        call_command("picture_dictionary", "ensure", community_id=self.community.id, organiser=self.organiser.username)
        dictionary = PictureDictionary.objects.get(community=self.community)
        dictionary.project.page_image_text_source = Project.PAGE_IMAGE_TEXT_SOURCE_TRANSLATION
        dictionary.project.save(update_fields=["page_image_text_source", "updated_at"])
        call_command("picture_dictionary", "add", community_id=self.community.id, organiser=self.organiser.username, words="Katze")
        run_dir = dictionary.project.artifact_dir() / "runs" / "run_picture_dictionary"
        gloss_payload = read_stage_artifact(run_dir, "gloss")
        gloss_payload["pages"][0]["segments"][0]["tokens"][0]["annotations"] = {
            "lemma": "Katze",
            "pos": "NOUN",
            "gloss": "cat",
            "translation": "cat",
        }
        write_stage_artifact(run_dir, "gloss", gloss_payload)
        call_command("picture_dictionary", "compile", community_id=self.community.id, organiser=self.organiser.username)
        page = dictionary.project.image_pages.order_by("page_number").first()
        assert page is not None
        self.assertEqual(page.page_text, "cat")

    def test_picture_dictionary_defaults_for_non_ai_language(self):
        self.community.language = "xkk"
        self.community.save(update_fields=["language"])
        call_command("picture_dictionary", "ensure", community_id=self.community.id, organiser=self.organiser.username)
        dictionary = PictureDictionary.objects.get(community=self.community)
        self.assertEqual(dictionary.project.page_image_text_source, Project.PAGE_IMAGE_TEXT_SOURCE_TRANSLATION)
        style = dictionary.project.image_style
        self.assertFalse(style.discourage_text_in_images)
        self.assertTrue(style.disallow_text_in_images)

    def test_manual_rows_pick_up_translation_stage_values(self):
        call_command("picture_dictionary", "ensure", community_id=self.community.id, organiser=self.organiser.username)
        dictionary = PictureDictionary.objects.get(community=self.community)
        call_command("picture_dictionary", "add", community_id=self.community.id, organiser=self.organiser.username, words="Katze")
        run_dir = dictionary.project.artifact_dir() / "runs" / "run_picture_dictionary"
        tr_payload = read_stage_artifact(run_dir, "translation")
        tr_payload["pages"][0]["segments"][0].setdefault("annotations", {})
        tr_payload["pages"][0]["segments"][0]["annotations"]["translation"] = "cat"
        write_stage_artifact(run_dir, "translation", tr_payload)
        entry = dictionary.entries.get(surface="Katze")
        rows = _manual_rows_from_entries(dictionary, [entry])
        self.assertEqual(rows[0]["translation"], "cat")
        self.assertEqual(rows[0]["gloss"], "cat")

    def test_import_project_as_dictionary_copy_filters_untranslated_pages_and_supports_picture_glossing(self):
        source = Project.objects.create(
            owner=self.organiser,
            title="50 words in Kok Kaper",
            source_text="50 words in Kok Kaper\nKatze\nHund",
            language="de",
            target_language="en",
            community=self.community,
            access_scope=Project.ACCESS_COMMUNITY,
        )
        run_dir = source.artifact_dir() / "runs" / "run_import_seed"
        payload = {
            "l2": "de",
            "l1": "en",
            "surface": "50 words in Kok Kaper<page>Katze<page>Hund",
            "pages": [
                {
                    "surface": "50 words in Kok Kaper",
                    "segments": [
                        {
                            "surface": "50 words in Kok Kaper",
                            "tokens": [
                                {"surface": "50"},
                                {"surface": "words"},
                                {"surface": "in"},
                                {"surface": "Kok"},
                                {"surface": "Kaper"},
                            ],
                            "annotations": {"translation": "50 words in Kok Kaper"},
                        }
                    ],
                    "annotations": {},
                },
                {
                    "surface": "Katze",
                    "segments": [
                        {
                            "surface": "Katze",
                            "tokens": [
                                {
                                    "surface": "Katze",
                                    "annotations": {"lemma": "Katze", "pos": "NOUN", "gloss": "cat"},
                                }
                            ],
                            "annotations": {},
                        }
                    ],
                    "annotations": {},
                },
                {
                    "surface": "Hund",
                    "segments": [
                        {
                            "surface": "Hund",
                            "tokens": [
                                {
                                    "surface": "Hund",
                                    "annotations": {"lemma": "Hund", "pos": "NOUN", "gloss": "dog"},
                                }
                            ],
                            "annotations": {},
                        }
                    ],
                    "annotations": {"generated_image": {"path": "images/pages/page_003/variant_001.png"}},
                },
            ],
            "annotations": {},
        }
        write_stage_artifact(run_dir, "gloss", payload)
        for page_number, word in [(2, "Katze"), (3, "Hund")]:
            rel = f"images/pages/page_{page_number:03d}/variant_001.png"
            image_path = source.artifact_dir() / rel
            image_path.parent.mkdir(parents=True, exist_ok=True)
            image_path.write_bytes(f"fake-{word}".encode("utf-8"))
            if page_number == 2:
                ProjectImagePage.objects.create(
                    project=source,
                    page_number=page_number,
                    page_text=word,
                    generation_prompt=word,
                    image_path=rel,
                    status=ProjectImagePage.STATUS_APPROVED,
                )

        call_command(
            "picture_dictionary",
            "import-project",
            community_id=self.community.id,
            organiser=self.organiser.username,
            source_project_id=source.id,
        )

        dictionary = PictureDictionary.objects.get(community=self.community)
        self.assertNotEqual(dictionary.project_id, source.id)
        entries = list(dictionary.entries.filter(is_active=True).order_by("current_page_number"))
        self.assertEqual([entry.surface for entry in entries], ["Katze", "Hund"])
        self.assertEqual([entry.current_page_number for entry in entries], [1, 2])
        self.assertNotIn("50", dictionary.project.source_text)
        self.assertEqual(dictionary.project.image_pages.count(), 2)
        copied_image = dictionary.project.artifact_dir() / entries[0].image_path
        self.assertTrue(copied_image.exists())
        annotation_image = dictionary.project.artifact_dir() / entries[1].image_path
        self.assertTrue(annotation_image.exists())
        filtered_stage = dictionary.project.artifact_dir() / "runs" / "run_picture_dictionary" / "stages" / "segmentation_phase_1.json"
        self.assertTrue(filtered_stage.exists())
        self.assertNotIn("50 words in Kok Kaper", filtered_stage.read_text(encoding="utf-8"))
        imported_gloss = read_stage_artifact(dictionary.project.artifact_dir() / "runs" / "run_picture_dictionary", "gloss")
        tokens = [
            token
            for page in imported_gloss["pages"]
            for segment in page["segments"]
            for token in segment["tokens"]
        ]
        self.assertEqual([token["annotations"].get("gloss") for token in tokens], ["cat", "dog"])

        call_command(
            "picture_dictionary",
            "compile",
            community_id=self.community.id,
            organiser=self.organiser.username,
        )
        compiled_gloss = read_stage_artifact(dictionary.project.artifact_dir() / "runs" / "run_picture_dictionary", "gloss")
        compiled_tokens = [
            token
            for page in compiled_gloss["pages"]
            for segment in page["segments"]
            for token in segment["tokens"]
        ]
        self.assertEqual([token["annotations"].get("gloss") for token in compiled_tokens], ["cat", "dog"])

        summary_path = dictionary.project.artifact_dir() / "picture_dictionary_import" / "summary.json"
        self.assertTrue(summary_path.exists())
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        self.assertEqual(summary["entries_created"], 2)
        self.assertEqual(summary["page_map"], {"2": 1, "3": 2})

        toy_project = Project.objects.create(
            owner=self.organiser,
            title="Toy German Text",
            source_text="Die Katze schläft.",
            language="de",
            target_language="en",
            community=self.community,
        )
        output_dir = toy_project.artifact_dir() / "runs" / "run_test_imported_dictionary_gloss"
        output_dir.mkdir(parents=True, exist_ok=True)
        glosses = _build_picture_glosses_for_compile(project=toy_project, output_dir=output_dir)
        self.assertIn("katze", glosses)
        self.assertTrue((output_dir / "html" / glosses["katze"]["image_path"]).exists())

    def test_non_organiser_cannot_manage_dictionary(self):
        with self.assertRaises(CommandError):
            call_command(
                "picture_dictionary",
                "ensure",
                community_id=self.community.id,
                organiser=self.member.username,
            )

    def test_remove_keeps_registry_and_marks_entries_inactive(self):
        call_command(
            "picture_dictionary",
            "ensure",
            community_id=self.community.id,
            organiser=self.organiser.username,
        )
        dictionary = PictureDictionary.objects.get(community=self.community)
        call_command(
            "picture_dictionary",
            "add",
            community_id=self.community.id,
            organiser=self.organiser.username,
            words="chat, chien",
        )
        entry = PictureDictionaryEntry.objects.get(dictionary=dictionary, surface="chat")
        call_command(
            "picture_dictionary",
            "remove",
            community_id=self.community.id,
            organiser=self.organiser.username,
            words="chat",
        )
        entry.refresh_from_db()
        self.assertFalse(entry.is_active)
        call_command(
            "picture_dictionary",
            "compile",
            community_id=self.community.id,
            organiser=self.organiser.username,
        )
        dictionary.refresh_from_db()
        for stage_name in ("lemma", "gloss", "romanization", "pinyin"):
            stage_path = dictionary.project.artifact_dir() / "runs" / "run_picture_dictionary" / "stages" / f"{stage_name}.json"
            self.assertNotIn("chat", stage_path.read_text(encoding="utf-8"))

    def test_cross_project_picture_glosses_are_staged_into_compile_html_dir(self):
        call_command(
            "picture_dictionary",
            "ensure",
            community_id=self.community.id,
            organiser=self.organiser.username,
        )
        dictionary = PictureDictionary.objects.get(community=self.community)
        entry = PictureDictionaryEntry.objects.create(
            dictionary=dictionary,
            surface="femme",
            lemma="femme",
            pos="NOUN",
            is_active=True,
        )
        image_rel = "images/pages/page_002/variant_001.png"
        image_abs = dictionary.project.artifact_dir() / image_rel
        image_abs.parent.mkdir(parents=True, exist_ok=True)
        image_abs.write_bytes(b"fake-image")
        entry.image_path = image_rel
        entry.save(update_fields=["image_path", "updated_at"])

        toy_project = Project.objects.create(
            owner=self.organiser,
            title="Toy French Text",
            source_text="La femme parle.",
            language="fr",
            target_language="en",
            community=self.community,
        )
        output_dir = toy_project.artifact_dir() / "runs" / "run_test_cross_project_gloss"
        output_dir.mkdir(parents=True, exist_ok=True)
        diagnostics: list[str] = []
        glosses = _build_picture_glosses_for_compile(
            project=toy_project,
            output_dir=output_dir,
            diagnostics=diagnostics,
        )
        self.assertIn("femme", glosses)
        self.assertTrue(any("active_entries=1" in message and "mapped=1" in message for message in diagnostics))
        self.assertTrue(any("mapped sample" in message for message in diagnostics))
        rel_path = glosses["femme"]["image_path"]
        self.assertTrue(rel_path.startswith("picture_glosses/"))
        staged = output_dir / "html" / Path(rel_path)
        self.assertTrue(staged.exists())

    def test_picture_gloss_diagnostics_report_missing_and_duplicate_entries(self):
        call_command(
            "picture_dictionary",
            "ensure",
            community_id=self.community.id,
            organiser=self.organiser.username,
        )
        dictionary = PictureDictionary.objects.get(community=self.community)
        image_rel = "images/pages/page_001/variant_001.png"
        image_abs = dictionary.project.artifact_dir() / image_rel
        image_abs.parent.mkdir(parents=True, exist_ok=True)
        image_abs.write_bytes(b"fake-image")
        PictureDictionaryEntry.objects.create(
            dictionary=dictionary,
            surface="eins",
            lemma="eins",
            image_path=image_rel,
            is_active=True,
        )
        PictureDictionaryEntry.objects.create(
            dictionary=dictionary,
            surface="eins duplicate",
            lemma="eins",
            image_path=image_rel,
            is_active=True,
        )
        PictureDictionaryEntry.objects.create(
            dictionary=dictionary,
            surface="zwei",
            lemma="zwei",
            is_active=True,
        )
        PictureDictionaryEntry.objects.create(
            dictionary=dictionary,
            surface="drei",
            lemma="drei",
            image_path="images/pages/page_003/missing.png",
            is_active=True,
        )
        toy_project = Project.objects.create(
            owner=self.organiser,
            title="Toy diagnostics text",
            source_text="eins zwei drei",
            language="de",
            target_language="en",
            community=self.community,
        )
        output_dir = toy_project.artifact_dir() / "runs" / "run_test_gloss_diagnostics"
        output_dir.mkdir(parents=True, exist_ok=True)
        diagnostics: list[str] = []

        glosses = _build_picture_glosses_for_compile(
            project=toy_project,
            output_dir=output_dir,
            diagnostics=diagnostics,
        )

        self.assertEqual(list(glosses.keys()), ["eins"])
        summary = "\n".join(diagnostics)
        self.assertIn("active_entries=4", summary)
        self.assertIn("mapped=1", summary)
        self.assertIn("entry_image_paths_before_fallback=3", summary)
        self.assertIn("entry_page_numbers=0", summary)
        self.assertIn("dictionary_pages=0", summary)
        self.assertIn("duplicate_lemma=1", summary)
        self.assertIn("missing_image_path=1", summary)
        self.assertIn("missing_image_file=1", summary)
        self.assertIn("missing_image_path sample", summary)
        self.assertIn("missing_image_file sample", summary)

    def test_cross_project_picture_glosses_fallback_to_dictionary_page_image_path(self):
        call_command(
            "picture_dictionary",
            "ensure",
            community_id=self.community.id,
            organiser=self.organiser.username,
        )
        dictionary = PictureDictionary.objects.get(community=self.community)
        entry = PictureDictionaryEntry.objects.create(
            dictionary=dictionary,
            surface="chat",
            lemma="chat",
            pos="NOUN",
            is_active=True,
            current_page_number=1,
        )
        dictionary.project.image_pages.create(
            page_number=1,
            page_text="chat",
            generation_prompt="chat",
            image_model="gpt-image-1",
            image_path="images/pages/page_001/variant_001.png",
        )
        image_abs = dictionary.project.artifact_dir() / "images/pages/page_001/variant_001.png"
        image_abs.parent.mkdir(parents=True, exist_ok=True)
        image_abs.write_bytes(b"fake-image")

        toy_project = Project.objects.create(
            owner=self.organiser,
            title="Toy French Text 2",
            source_text="Le chat dort.",
            language="fr",
            target_language="en",
            community=self.community,
        )
        output_dir = toy_project.artifact_dir() / "runs" / "run_test_fallback_gloss"
        output_dir.mkdir(parents=True, exist_ok=True)
        diagnostics: list[str] = []
        glosses = _build_picture_glosses_for_compile(
            project=toy_project,
            output_dir=output_dir,
            diagnostics=diagnostics,
        )
        self.assertIn("chat", glosses)
        self.assertTrue(any("entry_image_paths_before_fallback=0" in message for message in diagnostics))
        self.assertTrue(any("dictionary_pages=1" in message for message in diagnostics))
        self.assertTrue(any("page_image_paths=1" in message for message in diagnostics))
        self.assertTrue(any("page_fallbacks=1" in message for message in diagnostics))
        entry.refresh_from_db()
        self.assertEqual(entry.image_path, "images/pages/page_001/variant_001.png")
