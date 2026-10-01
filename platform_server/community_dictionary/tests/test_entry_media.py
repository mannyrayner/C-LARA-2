from datetime import timedelta
import io
from pathlib import Path
import tempfile
from unittest.mock import patch
import uuid
import wave

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from community_dictionary import tts
from community_dictionary.models import AudioStudy, Contribution, Dictionary, Entry, Membership, Partner, Partnership, PhotoStudy, Request, VoicePreference
from community_dictionary.forms import DictionaryForm, DictionarySettingsForm
from community_dictionary.services import Conflict, accept, add_contributions
from community_dictionary.storage import path_for, prepare_upload
from community_dictionary.tests.test_photo_learning import response
from community_dictionary.tests.test_workflow import picture
from projects.models import AIUsageCharge, CreditAccount, Profile


def speech_fixture():
    """Audible PCM fixture, not a real provider or pronunciation test."""
    import math
    import struct
    stream = io.BytesIO()
    with wave.open(stream, 'wb') as output:
        output.setparams((1, 2, 24000, 0, 'NONE', 'not compressed'))
        output.writeframes(b''.join(struct.pack('<h', int(7000*math.sin(i*2*math.pi*440/24000))) for i in range(2400)))
    return (stream.getvalue(), 'audio/wav', '.wav'), .1


@override_settings(OPENAI_API_KEY='test-only', CREDITS_ENABLED=False)
class EntryMediaTests(TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup)
        settings = override_settings(COMMUNITY_DICTIONARY_MEDIA_ROOT=Path(temp.name)/'private',
            MEDIA_ROOT=Path(temp.name)/'public', PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
        settings.enable(); self.addCleanup(settings.disable)
        self.owner = get_user_model().objects.create_user('entry-owner', password='test')
        self.member = get_user_model().objects.create_user('entry-member', password='test')
        self.outsider = get_user_model().objects.create_user('entry-outsider', password='test')
        self.dictionary = Dictionary.objects.create(name='Swedish photos', language='Swedish', owner=self.owner,
            explanation_language='English', photo_ai_enabled=True, tts_enabled=True)
        Membership.objects.create(dictionary=self.dictionary, user=self.member, accepted=True)
        self.entry = Entry.objects.create(dictionary=self.dictionary, created_by=self.owner)
        made = add_contributions(self.entry, self.owner, {'prepared_photo': prepare_upload(picture(), 'image'),
            'word': 'häst', 'meaning': 'horse', 'category': 'animals'}, [], publish=True)
        self.entry.refresh_from_db()
        self.image = next(c for c in made if c.kind == 'image')
        self.client.force_login(self.owner)
        self.photo = patch('community_dictionary.photo_ai.analyse', return_value=response()).start()
        self.speech = patch('community_dictionary.tts.synthesize', return_value=speech_fixture()).start()
        self.addCleanup(patch.stopall)

    def url(self, name, *args):
        return reverse('community_dictionary:'+name, args=[self.dictionary.pk, *args])

    def interpret(self, token=None, **extra):
        return self.client.post(self.url('entry-photo', self.entry.pk, self.image.pk),
            {'submission_id': token or uuid.uuid4(), 'base_version': self.entry.text_version, 'ai_consent': 'on', **extra})

    def photo_save(self, study, **extra):
        self.client.post(self.url('photo-action', study.pk), {'action':'confirm'})
        return self.client.post(self.url('photo-action', study.pk),
            {'action':'save', 'word':'häst', 'meaning':'horse', 'consent':'on', 'publish_now':'on', **extra})

    def generate(self, token=None, **extra):
        return self.client.post(self.url('audio-start', self.entry.pk), {'submission_id':token or uuid.uuid4(),
            'source_text_id':self.entry.current_text_id, 'source_text_version':self.entry.text_version, 'ai_consent':'on', 'voice':'marin', **extra})

    def audio_study(self):
        result = self.generate()
        self.assertEqual(result.status_code, 302)
        return AudioStudy.objects.latest('created_at')

    def audio_save(self, study, **extra):
        return self.client.post(self.url('audio-action', study.pk), {'action':'save', 'consent':'on', 'publish_now':'on', **extra})

    def edit_words(self):
        add_contributions(self.entry, self.owner, {'word':'en häst', 'meaning':'horse',
            'base_version':self.entry.text_version}, [], publish=True)
        self.entry.refresh_from_db()

    def test_return_later_reuses_saved_image_and_same_entry(self):
        page = self.client.get(self.url('entry', self.entry.pk))
        self.assertContains(page, 'Learn from this photo')
        self.assertContains(page, 'Create spoken audio')
        page = self.client.get(self.url('entry-photo', self.entry.pk, self.image.pk))
        self.assertNotContains(page, 'type="file"')
        self.photo.assert_not_called()
        token = uuid.uuid4()
        self.assertEqual(self.interpret(token).status_code, 302)
        self.interpret(token)
        self.assertEqual(self.photo.call_count, 1)
        study = PhotoStudy.objects.get()
        self.assertEqual(self.photo.call_args.args[0], path_for(self.image.file_path).read_bytes())
        with self.captureOnCommitCallbacks(execute=True):
            result = self.photo_save(study)
        self.assertEqual(result.url, self.url('entry', self.entry.pk))
        self.entry.refresh_from_db()
        self.assertEqual(self.entry.category, 'animals')
        self.assertEqual(Entry.objects.count(), 1)
        self.assertEqual(Contribution.objects.filter(kind='image').count(), 1)
        self.assertTrue(path_for(self.image.file_path).exists())
        self.assertFalse(path_for(study.file_path).exists())
        self.photo_save(study)
        self.assertEqual(Contribution.objects.filter(kind='text').count(), 3)

    def test_source_scope_policy_consent_and_removed_image(self):
        self.assertEqual(self.interpret(ai_consent='').status_code, 200)
        other = Entry.objects.create(dictionary=self.dictionary, created_by=self.owner)
        self.assertEqual(self.client.get(self.url('entry-photo', other.pk, self.image.pk)).status_code, 404)
        self.client.force_login(self.outsider)
        self.assertEqual(self.interpret().status_code, 404)
        self.client.force_login(self.owner)
        self.image.status='removed'; self.image.save()
        self.assertEqual(self.interpret().status_code, 404)
        self.photo.assert_not_called()

    def test_old_interpretation_does_not_overwrite_new_words(self):
        self.interpret(); study=PhotoStudy.objects.get()
        self.edit_words()
        self.assertEqual(self.photo_save(study).status_code, 409)
        self.entry.refresh_from_db(); self.assertEqual(self.entry.word, 'en häst')

    def test_deleted_source_never_creates_replacement_entry(self):
        self.interpret(); study=PhotoStudy.objects.get()
        self.entry.delete()
        self.assertEqual(self.photo_save(study).status_code, 409)
        self.assertEqual(Entry.objects.count(), 0)

    def test_member_photo_wording_remains_reviewable(self):
        self.client.force_login(self.member)
        self.interpret(); study=PhotoStudy.objects.get()
        self.assertEqual(self.photo_save(study, word='en häst').status_code, 302)
        text=Contribution.objects.filter(kind='text').latest('pk')
        self.assertEqual(text.status, 'pending')
        self.assertEqual(text.base_version, self.entry.text_version)
        accept(text, self.owner)
        self.entry.refresh_from_db(); self.assertEqual(self.entry.word, 'en häst')

    def test_audio_preview_save_replay_and_persistent_range_playback(self):
        token=uuid.uuid4()
        result=self.generate(token); self.generate(token)
        study=AudioStudy.objects.get()
        self.assertEqual(study.status, 'ready')
        self.assertEqual(self.speech.call_count, 1)
        self.assertEqual(self.speech.call_args.args[0], 'häst')
        self.assertEqual(self.speech.call_args.kwargs['language'], 'sv')
        self.assertEqual(Contribution.objects.filter(kind='audio').count(), 0)
        page=self.client.get(result.url)
        self.assertContains(page, 'AI-generated voice')
        self.assertEqual(self.audio_save(study, consent='').status_code, 200)
        with self.captureOnCommitCallbacks(execute=True):
            self.assertEqual(self.audio_save(study).status_code, 302)
        self.audio_save(study)
        audio=Contribution.objects.get(kind='audio')
        self.assertEqual(audio.status, 'accepted')
        self.assertEqual(audio.provenance['source_text'], 'häst')
        self.assertFalse(path_for(study.file_path).exists())
        self.assertTrue(path_for(audio.file_path).exists())
        media=self.client.get(self.url('media', audio.pk), HTTP_RANGE='bytes=0-19')
        self.assertEqual(media.status_code,206)
        self.assertEqual(len(b''.join(media.streaming_content)),20)
        self.assertIn('no-store',media['Cache-Control'])
        self.assertEqual(AIUsageCharge.objects.filter(operation='community_tts').count(),1)
        AudioStudy.objects.update(expires_at=timezone.now()-timedelta(seconds=1))
        call_command('expire_photo_studies', stdout=io.StringIO())
        self.assertTrue(path_for(audio.file_path).exists())

    def test_audio_policy_consent_missing_words_language_and_csrf(self):
        self.assertEqual(self.generate(ai_consent='').status_code,200)
        self.dictionary.tts_enabled=False; self.dictionary.save()
        self.assertEqual(self.generate().status_code,403)
        self.dictionary.tts_enabled=True; self.dictionary.language='Pitjantjatjara'; self.dictionary.save()
        self.assertContains(self.generate(),'not configured for this language')
        self.dictionary.language='Swedish'; self.dictionary.save()
        self.entry.word=''; self.entry.save()
        self.assertContains(self.generate(),'Add and accept the wording')
        csrf=Client(enforce_csrf_checks=True); csrf.force_login(self.owner)
        self.assertEqual(csrf.post(self.url('audio-start',self.entry.pk),{}).status_code,403)
        self.speech.assert_not_called()

    def test_draft_audio_private_to_creator_and_revoked_member(self):
        self.client.force_login(self.member); study=self.audio_study()
        media=self.client.get(self.url('audio-media',study.pk), HTTP_RANGE='bytes=0-9')
        self.assertEqual(media.status_code,206); media.close()
        self.client.force_login(self.owner)
        for route in ['audio-study','audio-media','audio-action']:
            method=self.client.post if route=='audio-action' else self.client.get
            self.assertEqual(method(self.url(route,study.pk)).status_code,404)
        self.client.force_login(self.member)
        Membership.objects.filter(user=self.member).delete()
        self.assertEqual(self.client.get(self.url('audio-media',study.pk)).status_code,404)

    def test_audio_changes_before_generation_save_or_review(self):
        self.assertContains(self.generate(source_text_version=0),'wording changed')
        self.speech.assert_not_called()
        study=self.audio_study()
        self.edit_words()
        self.assertEqual(self.audio_save(study).status_code,409)
        self.client.force_login(self.member)
        study=self.audio_study(); self.audio_save(study)
        audio=Contribution.objects.get(kind='audio')
        self.assertEqual(audio.status,'pending')
        add_contributions(self.entry,self.owner,{'word':'häst','base_version':self.entry.text_version},[],publish=True)
        with self.assertRaises(Conflict): accept(audio,self.owner)

    def test_discard_and_expiry_remove_only_draft_audio(self):
        study=self.audio_study()
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(self.url('audio-action',study.pk),{'action':'discard'})
        self.assertFalse(path_for(study.file_path).exists())
        self.assertEqual(self.audio_save(study).status_code,409)
        study=self.audio_study()
        AudioStudy.objects.filter(pk=study.pk).update(expires_at=timezone.now()-timedelta(seconds=1))
        self.assertEqual(self.client.get(self.url('audio-media',study.pk)).status_code,404)
        call_command('expire_photo_studies',stdout=io.StringIO())
        self.assertFalse(path_for(study.file_path).exists())
        self.assertTrue(path_for(self.image.file_path).exists())

    @override_settings(COMMUNITY_DICTIONARY_TTS_DAILY_LIMIT=1)
    def test_audio_quota_counts_discarded_attempt(self):
        study=self.audio_study()
        self.client.post(self.url('audio-action',study.pk),{'action':'discard'})
        self.assertContains(self.generate(),'daily audio-generation limit')
        self.assertEqual(self.speech.call_count,1)

    def test_failure_and_processing_refresh_never_regenerate(self):
        self.speech.side_effect=TimeoutError('private-provider-error')
        token=uuid.uuid4(); self.generate(token); self.generate(token)
        study=AudioStudy.objects.get()
        self.assertEqual(study.status,'failed')
        self.assertEqual(self.speech.call_count,1)
        self.assertNotContains(self.client.get(self.url('audio-study',study.pk)),'private-provider-error')
        AudioStudy.objects.update(status='processing',created_at=timezone.now()-timedelta(minutes=2))
        self.assertContains(self.client.get(self.url('audio-study',study.pk)),'could not be recovered')
        self.assertEqual(self.speech.call_count,1)

    @override_settings(CREDITS_ENABLED=True)
    def test_credit_gate_and_single_estimated_charge(self):
        self.assertContains(self.generate(),'balance is too low')
        self.speech.assert_not_called()
        CreditAccount.objects.filter(user=self.owner).update(balance_usd='1.0000')
        token=uuid.uuid4(); self.generate(token); self.generate(token)
        charge=AIUsageCharge.objects.get(operation='community_tts')
        self.assertEqual(charge.total_tokens,0)
        self.assertIn('Estimated',charge.notes)
        self.assertEqual(charge.ledger_entry.metadata['cost_basis'],'duration_and_input_bytes_estimate')

    def test_personal_key_and_empty_key_do_not_charge_or_fall_back(self):
        profile,_=Profile.objects.get_or_create(user=self.owner)
        profile.use_personal_openai_key=True; profile.openai_api_key=''; profile.save()
        self.assertContains(self.generate(),'Add your OpenAI API key')
        self.speech.assert_not_called()
        profile.openai_api_key='personal-test'; profile.save()
        self.audio_study()
        self.assertEqual(AIUsageCharge.objects.count(),0)
        self.assertEqual(self.speech.call_args.kwargs['api_key'],'personal-test')

    def test_old_tts_moves_to_history_when_wording_changes(self):
        self.edit_words()  # Start with "en häst", as in Manny's report.
        study=self.audio_study(); self.audio_save(study)
        old=Contribution.objects.get(kind='audio')
        add_contributions(self.entry,self.owner,{'word':'häst','base_version':self.entry.text_version},[],publish=True)
        self.entry.refresh_from_db()
        page=self.client.get(self.url('entry',self.entry.pk))
        self.assertEqual(page.context['audio'],[])
        self.assertContains(page,'No accepted recording for this wording yet')
        self.assertContains(page,'Earlier generated audio')
        self.assertContains(page,'Spoken text: <span dir="auto">en häst</span>',html=True)
        # The old media is preserved in history, not deleted or regenerated.
        self.assertTrue(path_for(old.file_path).exists())
        old.refresh_from_db(); self.assertEqual(old.status,'accepted')
        self.assertEqual(self.speech.call_count,1)
        study=self.audio_study(); self.audio_save(study)
        current=Contribution.objects.filter(kind='audio').exclude(pk=old.pk).get()
        page=self.client.get(self.url('entry',self.entry.pk))
        self.assertEqual([c.pk for c in page.context['audio']],[current.pk])
        self.assertEqual(current.provenance['source_text'],'häst')

    def test_tts_survives_nonspoken_edits_and_returns_when_wording_restored(self):
        original=self.entry.current_text_id
        study=self.audio_study(); self.audio_save(study)
        audio=Contribution.objects.get(kind='audio')
        add_contributions(self.entry,self.owner,{'word':'häst','meaning':'a horse','category':'new category',
            'base_version':self.entry.text_version},[],publish=True)
        self.entry.refresh_from_db()
        page=self.client.get(self.url('entry',self.entry.pk))
        self.assertEqual([c.pk for c in page.context['audio']],[audio.pk])
        self.assertNotContains(page,'Earlier generated audio')
        self.edit_words()
        self.assertEqual(self.client.get(self.url('entry',self.entry.pk)).context['audio'],[])
        result=self.client.post(self.url('review',original),{'action':'restore','version':self.entry.text_version})
        self.assertEqual(result.status_code,302)
        page=self.client.get(self.url('entry',self.entry.pk))
        self.assertEqual([c.pk for c in page.context['audio']],[audio.pk])
        self.assertEqual(self.speech.call_count,1)

    def test_language_change_hides_tts_but_keeps_human_audio(self):
        study=self.audio_study(); self.audio_save(study)
        human=add_contributions(self.entry,self.owner,{'prepared_audio':speech_fixture()[0]},[],publish=True)[0]
        self.dictionary.language='Italian'; self.dictionary.save()
        page=self.client.get(self.url('entry',self.entry.pk))
        self.assertEqual([c.pk for c in page.context['audio']],[human.pk])
        self.assertContains(page,'Earlier generated audio')
        self.dictionary.language='Swedish'; self.dictionary.save()
        page=self.client.get(self.url('entry',self.entry.pk))
        self.assertEqual(len(page.context['audio']),2)
        self.assertNotContains(page,'Earlier generated audio')

    def test_browse_and_partnership_samples_exclude_old_tts(self):
        study=self.audio_study(); self.audio_save(study)
        self.edit_words()
        group=Partnership.objects.create(dictionary=self.dictionary,name='Partners',created_by=self.owner)
        Partner.objects.create(partnership=group,user=self.owner,accepted=True)
        Request.objects.create(entry=self.entry,partnership=group,kind='image',created_by=self.owner)
        for route,key in [('dictionary','cards'),('queue','rows')]:
            page=self.client.get(self.url(route))
            self.assertEqual(len(page.context[key]),1)
            self.assertIsNone(page.context[key][0]['sample_audio'])
        study=self.audio_study(); self.audio_save(study)
        current=Contribution.objects.filter(kind='audio').latest('created_at')
        for route,key in [('dictionary','cards'),('queue','rows')]:
            page=self.client.get(self.url(route))
            self.assertEqual(page.context[key][0]['sample_audio'].pk,current.pk)

    def test_new_dictionary_defaults_visible_and_can_be_disabled(self):
        form = DictionaryForm()
        self.assertTrue(form['photo_ai_enabled'].value())
        self.assertTrue(form['tts_enabled'].value())
        result = self.client.post(reverse('community_dictionary:home'), {'name':'New Swedish',
            'language':'Swedish', 'photo_ai_enabled':'on', 'tts_enabled':'on'})
        self.assertEqual(result.status_code,302)
        new = Dictionary.objects.get(name='New Swedish')
        self.assertTrue(new.photo_ai_enabled); self.assertTrue(new.tts_enabled)
        result = self.client.post(reverse('community_dictionary:home'), {'name':'Human only','language':'Pitjantjatjara'})
        self.assertEqual(result.status_code,302)
        human = Dictionary.objects.get(name='Human only')
        self.assertFalse(human.photo_ai_enabled); self.assertFalse(human.tts_enabled)
        settings = DictionarySettingsForm(instance=human)
        self.assertFalse(settings['photo_ai_enabled'].value())
        self.assertFalse(settings['tts_enabled'].value())

    def test_new_dictionary_does_not_offer_unsupported_speech_silently(self):
        result = self.client.post(reverse('community_dictionary:home'), {'name':'Unsupported',
            'language':'Pitjantjatjara', 'tts_enabled':'on'})
        self.assertContains(result,'Saved TTS is not configured for this language')
        self.assertFalse(Dictionary.objects.filter(name='Unsupported').exists())

    def test_selected_voice_is_recorded_saved_and_remembered(self):
        page = self.client.get(self.url('audio-start', self.entry.pk))
        self.assertEqual(page.context['form']['voice'].value(),'marin')
        result = self.generate(voice='cedar')
        self.assertEqual(result.status_code,302)
        self.assertEqual(self.speech.call_args.kwargs['voice'],'cedar')
        study = AudioStudy.objects.get()
        self.assertEqual(study.voice,'cedar')
        self.audio_save(study)
        self.assertEqual(Contribution.objects.get(kind='audio').provenance['voice'],'cedar')
        self.assertContains(self.client.get(self.url('entry',self.entry.pk)),'Cedar')
        AudioStudy.objects.update(expires_at=timezone.now()-timedelta(seconds=1))
        call_command('expire_photo_studies',stdout=io.StringIO())
        # Preference survives draft cleanup and a fresh browser session.
        fresh = Client(); fresh.force_login(self.owner)
        self.assertEqual(fresh.get(self.url('audio-start',self.entry.pk)).context['form']['voice'].value(),'cedar')
        self.client.force_login(self.member)
        self.assertEqual(self.client.get(self.url('audio-start',self.entry.pk)).context['form']['voice'].value(),'marin')
        self.assertEqual(VoicePreference.objects.count(),1)

    def test_invalid_voice_and_changed_receipt_never_invoke_provider(self):
        self.assertContains(self.generate(voice='unknown-voice'),'Select a valid choice')
        self.speech.assert_not_called()
        token=uuid.uuid4(); self.generate(token,voice='cedar')
        self.assertContains(self.generate(token,voice='marin'),'submission has changed')
        self.assertEqual(self.speech.call_count,1)
        self.assertEqual(VoicePreference.objects.get().voice,'cedar')

    def test_saved_tts_flow_does_not_switch_to_device_voice(self):
        self.interpret(); study=PhotoStudy.objects.get()
        self.client.post(self.url('photo-action',study.pk),{'action':'confirm'})
        page=self.client.get(self.url('photo-study',study.pk))
        self.assertNotContains(page,'data-photo-speak')
        self.assertContains(page,'Create spoken audio')
        self.dictionary.tts_enabled=False; self.dictionary.save()
        self.assertContains(self.client.get(self.url('photo-study',study.pk)),'data-photo-speak')


class SavedSpeechContractTests(TestCase):
    def test_real_engine_adapter_keeps_language_edited_text_and_no_retries(self):
        with patch('community_dictionary.tts._openai_client') as sdk:
            stream=sdk.return_value.__enter__.return_value.audio.speech.with_streaming_response.create
            stream.return_value.__enter__.return_value.stream_to_file.side_effect=lambda path: Path(path).write_bytes(speech_fixture()[0][0])
            prepared,duration=tts.synthesize('häst',language='sv',model=tts.MODEL,voice=tts.VOICE,api_key='test')
            self.assertEqual(prepared[1],'audio/wav')
            self.assertEqual(duration,.1)
            self.assertEqual(sdk.call_args.kwargs['max_retries'],0)
            self.assertEqual(stream.call_count,1)
            self.assertEqual(stream.call_args.kwargs['input'],'häst')
            self.assertIn('Swedish',stream.call_args.kwargs['instructions'])
            self.assertNotIn('photo',stream.call_args.kwargs)
            stream.side_effect=TypeError('instructions not supported')
            with self.assertRaises(TypeError):
                tts.synthesize('häst',language='sv',model=tts.MODEL,voice=tts.VOICE,api_key='test')
            self.assertEqual(stream.call_count,2)  # No second request without language instructions.

    def test_wav_validation_and_streaming_header_repair(self):
        good=speech_fixture()[0][0]
        streaming=bytearray(good); streaming[4:8]=b'\xff'*4; streaming[40:44]=b'\xff'*4
        normalized,duration=tts.normalize_wav(bytes(streaming))
        self.assertEqual(normalized[0],good); self.assertEqual(duration,.1)
        for data in [b'',b'<html>error</html>',good[:44]+bytes(len(good)-44)]:
            with self.assertRaises((ValueError,wave.Error,EOFError)): tts.normalize_wav(data)

    def test_alternate_named_voice_reaches_real_engine_adapter(self):
        with patch('community_dictionary.tts._openai_client') as sdk:
            stream=sdk.return_value.__enter__.return_value.audio.speech.with_streaming_response.create
            stream.return_value.__enter__.return_value.stream_to_file.side_effect=lambda path: Path(path).write_bytes(speech_fixture()[0][0])
            tts.synthesize('häst',language='sv',model=tts.MODEL,voice='cedar',api_key='test')
            self.assertEqual(stream.call_args.kwargs['voice'],'cedar')
            with self.assertRaises(ValueError):
                tts.synthesize('häst',language='sv',model=tts.MODEL,voice='made-up',api_key='test')
            self.assertEqual(stream.call_count,1)
