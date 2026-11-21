from unittest.mock import patch
from django.test import TestCase, override_settings
from community_dictionary import services
from community_dictionary.lexicon import recordings
from community_dictionary.models import AudioStudy, Contribution, Entry, Event
from community_dictionary.services import accept, add_contributions, Conflict
from community_dictionary.storage import path_for, prepare_upload
from . import test_entry_media as media

speech_fixture = media.speech_fixture


@override_settings(OPENAI_API_KEY='test-only', CREDITS_ENABLED=False)
class TTSReplacementTests(TestCase):
    setUp = media.EntryMediaTests.setUp
    url = media.EntryMediaTests.url
    generate = media.EntryMediaTests.generate
    audio_study = media.EntryMediaTests.audio_study
    audio_save = media.EntryMediaTests.audio_save
    edit_words = media.EntryMediaTests.edit_words

    def saved(self):
        study = self.audio_study()
        self.assertEqual(self.audio_save(study).status_code, 302)
        study.refresh_from_db()
        return study.saved_contribution

    def fixture_audio(self, entry=None, **provenance):
        clip = add_contributions(entry or self.entry, self.owner,
            {'prepared_audio': speech_fixture()[0]}, [], publish=True)[0]
        if provenance:
            clip.provenance = provenance
            clip.save(update_fields=['provenance'])
        return clip

    def test_sentence_replacement_preserves_human_forms_other_entries_and_history(self):
        self.entry.entry_type='sentence'; self.entry.save(update_fields=['entry_type'])
        # Earlier captures and earlier manual generations can both be active
        # on an entry made before this repair. Model both legacy variants.
        old = [self.fixture_audio(origin='synthetic', source_text=self.entry.word,
            language=self.dictionary.language, provider=provider) for provider in ['openai','google']]
        human = self.fixture_audio()
        form = Contribution.objects.create(entry=self.entry, author=self.owner, kind='form', status='accepted', word='form')
        form_audio = self.fixture_audio(origin='synthetic', sentence_form=form.pk)
        untagged_form_audio = self.fixture_audio(origin='synthetic')
        untagged_form_audio.shared_from=form; untagged_form_audio.save(update_fields=['shared_from'])
        other = Entry.objects.create(dictionary=self.dictionary, created_by=self.owner)
        other_audio = self.fixture_audio(other, origin='synthetic')
        study = self.audio_study()
        for clip in old:
            clip.refresh_from_db(); self.assertEqual(clip.status,'accepted')
        page=self.client.get(self.url('audio-study',study.pk))
        self.assertContains(page,'Human recordings are kept.')
        self.assertEqual(self.audio_save(study).status_code,302)
        study.refresh_from_db(); new=study.saved_contribution
        self.assertEqual(new.status,'accepted')
        self.assertEqual(new.provenance['replaces_audio_ids'],[c.pk for c in old])
        for clip in old:
            clip.refresh_from_db(); self.assertEqual(clip.status,'superseded')
            self.assertTrue(path_for(clip.file_path).is_file())
        for clip in [human,form_audio,untagged_form_audio,other_audio]:
            clip.refresh_from_db(); self.assertEqual(clip.status,'accepted')
        self.assertEqual({c.pk for c in recordings(self.entry,self.dictionary) if c.pk in [new.pk,*[c.pk for c in old]]},{new.pk})
        reading, history = self.client.get(self.url('entry',self.entry.pk)).content.decode().split(
            '<details class="panel" id="entry-options">',1)
        for clip in old:
            self.assertNotIn(self.url('media',clip.pk),reading)
            self.assertIn(self.url('media',clip.pk),history)
            media_response=self.client.get(self.url('media',clip.pk),HTTP_RANGE='bytes=0-9')
            self.assertEqual(media_response.status_code,206); media_response.close()
        for clip in [human,new]: self.assertIn(self.url('media',clip.pk),reading)
        self.assertEqual(Event.objects.filter(action='audio_replacement').count(),1)
        self.audio_save(study)
        self.assertEqual(Event.objects.filter(action='audio_replacement').count(),1)
        self.assertEqual(self.speech.call_count,1)

    def test_word_regeneration_also_selects_one_current_synthetic_recording(self):
        old=self.saved(); new=self.saved()
        old.refresh_from_db(); self.assertEqual(old.status,'superseded')
        self.assertEqual([c.pk for c in recordings(self.entry,self.dictionary)],[new.pk])
        self.assertEqual(self.speech.call_count,2)

    def test_member_pending_replacement_waits_for_editor_acceptance(self):
        old=self.saved(); human=self.fixture_audio()
        self.client.force_login(self.member)
        new=self.saved()  # forged publish_now cannot grant editor rights
        self.assertEqual(new.status,'pending')
        old.refresh_from_db(); self.assertEqual(old.status,'accepted')
        self.assertEqual({c.pk for c in recordings(self.entry,self.dictionary)},{old.pk,human.pk})
        accept(new,self.owner); new.refresh_from_db(); old.refresh_from_db()
        self.assertEqual((new.status,old.status),('accepted','superseded'))
        self.assertEqual({c.pk for c in recordings(self.entry,self.dictionary)},{new.pk,human.pk})
        accept(new,self.owner)
        self.assertEqual(Event.objects.filter(action='audio_replacement').count(),1)
        self.assertEqual(self.speech.call_count,2)

    def test_failed_discarded_and_stale_previews_keep_existing_recordings(self):
        old=self.saved()
        self.speech.side_effect=TimeoutError
        failed=self.audio_study(); self.assertEqual(failed.status,'failed')
        self.assertEqual(self.audio_save(failed).status_code,409)
        self.speech.side_effect=None
        discarded=self.audio_study()
        self.client.post(self.url('audio-action',discarded.pk),{'action':'discard'})
        stale=self.audio_study(); self.edit_words()
        self.assertEqual(self.audio_save(stale).status_code,409)
        old.refresh_from_db(); self.assertEqual(old.status,'accepted')
        self.assertTrue(path_for(old.file_path).exists())
        self.assertEqual(Event.objects.filter(action='audio_replacement').count(),0)

    def test_stale_pending_approval_cannot_supersede_existing_audio(self):
        old=self.saved(); self.client.force_login(self.member); pending=self.saved()
        self.edit_words()
        with self.assertRaises(Conflict): accept(pending,self.owner)
        old.refresh_from_db(); pending.refresh_from_db()
        self.assertEqual((old.status,pending.status),('accepted','pending'))
        self.assertEqual(Event.objects.filter(action='audio_replacement').count(),0)

    def test_transaction_failure_rolls_back_replacement_and_can_save_without_regeneration(self):
        old=self.saved(); study=self.audio_study(); original_event=services.event
        def audit_failure(dictionary,user,action,*args,**kwargs):
            if action=='audio_replacement': raise RuntimeError('fixture rollback')
            return original_event(dictionary,user,action,*args,**kwargs)
        with self.assertLogs('django.request',level='ERROR'), patch('community_dictionary.services.event',side_effect=audit_failure):
            with self.assertRaises(RuntimeError): self.audio_save(study)
        old.refresh_from_db(); study.refresh_from_db()
        self.assertEqual((old.status,study.status),('accepted','ready'))
        self.assertTrue(path_for(old.file_path).exists())
        self.assertTrue(path_for(study.file_path).exists())
        self.assertEqual(self.audio_save(study).status_code,302)
        self.assertEqual(self.speech.call_count,2)

    def test_copied_replacement_provenance_does_not_replace_again(self):
        old=self.saved()
        copied=Contribution.objects.create(entry=self.entry,author=self.owner,kind='audio',
            file_path=old.file_path,mime_type=old.mime_type,provenance=old.provenance)
        accept(copied,self.owner); old.refresh_from_db()
        self.assertEqual(old.status,'accepted')
        self.assertEqual(Event.objects.filter(action='audio_replacement').count(),0)
