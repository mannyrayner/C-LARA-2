"""Offline tests of Google routing, reversible batches and contributor protection."""
import uuid
from unittest.mock import Mock, patch
from django.test import TestCase, SimpleTestCase, override_settings
from django.urls import reverse
from community_dictionary import (audio_review, google_tts, google_word_audio as batch,
    word_audio, porting, port_tasks, sentence_forms as sf, tts)
from community_dictionary.models import Contribution, DictionaryWordAudioSettings, PictureCapture, SentenceWord
from community_dictionary.services import Conflict
from community_dictionary.participation import withdraw_all
from projects.models import AIUsageCharge, CreditLedgerEntry
from . import test_homograph_experiments as original
from . import test_provider_comparison as comparison_tests
from .test_mwe_audio import carrier_wave


@override_settings(COMMUNITY_DICTIONARY_GOOGLE_TTS_ENABLED=True, OPENAI_API_KEY='fixture-only',
    CREDITS_ENABLED=True, COMMUNITY_DICTIONARY_PORT_WINDOW=2)
class GoogleWordAudioTests(TestCase):
    seed = original.ExperimentTests.seed
    approve = original.ExperimentTests.approve
    synthesis = staticmethod(original.ExperimentTests.synthesis)

    def setUp(self):
        original.ExperimentTests.setUp(self)
        self.owner.is_staff = True; self.owner.save()
        self.choice = DictionaryWordAudioSettings.objects.create(dictionary=self.dictionary,
            authorised_by=self.owner, language='French', voice='fr-FR-Wavenet-F')
        auth = patch.object(google_tts, 'credentials', return_value=Mock())
        auth.start(); self.addCleanup(auth.stop)

    def finish(self, run):
        def google(text, **kw):
            kw['before_request']()
            kw['report'].update(provider='google', model=kw['selected_voice'], voice=kw['selected_voice'],
                instructions_version=google_tts.VERSION, speech_cost_usd=str(google_tts.estimate(text,kw['method'])),
                attempts=[{'outcome':'usable'}])
            return (carrier_wave(), 'audio/wav', '.wav'), 3.2
        return comparison_tests.ProviderComparisonTests.finish(self, run, google_fn=google)

    def quote(self, **kwargs):
        return batch.quote(self.owner, self.dictionary, uuid.uuid4(), **kwargs)

    def audio(self, entry, *, human=False, reviewed=False):
        from community_dictionary.storage import write_upload
        return Contribution.objects.create(entry=entry, author=self.owner, kind='audio', status='accepted',
            shared_from=entry.current_text, provenance={'origin':'human' if human else 'synthetic',
                'source_text':entry.word,'language':'French', 'pronunciation_approved':reviewed},
            **write_upload((carrier_wave(),'audio/wav','.wav'), self.dictionary.pk, []))

    def test_quote_includes_ordinary_lemmas_forms_and_expressions_no_network(self):
        word = self.seed('courir','run'); self.seed('de l’autre côté','on the other side')
        sentence = self.seed('Il court.','He runs.',kind='sentence')
        link = SentenceWord.objects.create(sentence_text=sentence.current_text,word_entry=word,
            word_text=word.current_text,surface='court')
        sf.publish(link,'runs',self.owner,{'origin':'synthetic'})
        with patch.object(google_tts,'client') as client:
            run = self.quote()
        client.assert_not_called(); self.assertFalse(CreditLedgerEntry.objects.exists())
        self.assertEqual({r['word'] for i in run.items.all() for r in i.snapshot['words']},
                         {'courir','court','de l’autre côté'})
        self.assertLess(run.allowance_usd, .01)

    def test_batch_publishes_google_metadata_and_restore_is_idempotent(self):
        entry = self.seed('four','oven'); old = self.audio(entry)
        run = self.quote(); self.approve(run); calls = self.finish(run)
        self.assertEqual(calls[0].call_count,1)
        self.assertEqual(Contribution.objects.filter(entry=entry,kind='audio',status='accepted').get().pk,old.pk)
        self.assertEqual(batch.apply_all(self.owner,run),(1,0))
        new = Contribution.objects.get(entry=entry,kind='audio',status='accepted')
        self.assertEqual(new.provenance['provider'],'google')
        self.assertEqual(new.provenance['voice'],'fr-FR-Wavenet-F')
        self.assertFalse(new.provenance['pronunciation_approved'])
        self.assertEqual(batch.apply_all(self.owner,run),(0,0))
        self.assertEqual(batch.restore(self.owner,run),(1,0))
        old.refresh_from_db(); self.assertEqual(old.status,'accepted')
        self.assertEqual(batch.restore(self.owner,run),(0,0))
        self.assertEqual(AIUsageCharge.objects.filter(provider='google').count(),1)

    def test_human_reviewed_and_already_matching_audio_are_skipped(self):
        human = self.seed('chat','cat'); self.audio(human,human=True)
        reviewed = self.seed('chien','dog'); self.audio(reviewed,reviewed=True)
        eligible = self.seed('four','oven')
        groups, skipped = batch.groups(self.dictionary)
        self.assertEqual(skipped,2); self.assertEqual(groups[0][0]['id'],eligible.current_text_id)
        run=self.quote(); self.approve(run); self.finish(run); batch.apply_all(self.owner,run)
        self.assertEqual(batch.groups(self.dictionary)[0],[])
        self.assertEqual(len(batch.groups(self.dictionary,include_reviewed=True,include_matching=True)[0]),2)

    def test_source_change_during_generation_never_replaces_audio(self):
        entry=self.seed(); old=self.audio(entry);run=self.quote();self.approve(run)
        Contribution.objects.filter(pk=entry.current_text_id).update(word='changed')
        self.finish(run)
        self.assertEqual(batch.apply_all(self.owner,run),(0,0))
        old.refresh_from_db();self.assertEqual(old.status,'accepted')

    def test_withdrawal_prevents_restore(self):
        entry=self.seed(author=self.member);self.audio(entry);run=self.quote();self.approve(run);self.finish(run)
        batch.apply_all(self.owner,run)
        withdraw_all(self.member,self.dictionary.pk,self.dictionary.membership_revision)
        done, _ = batch.restore(self.owner,run)
        self.assertEqual(done,0)
        self.assertFalse(Contribution.objects.filter(entry=entry,kind='audio',status='accepted').exists())

    def test_new_human_recording_blocks_batch_accept(self):
        entry=self.seed();run=self.quote();self.approve(run);self.finish(run)
        human=self.audio(entry,human=True)
        self.assertEqual(batch.apply_all(self.owner,run),(0,1))
        self.assertEqual(Contribution.objects.filter(entry=entry,kind='audio',status='accepted').get().pk,human.pk)

    def test_policy_change_stops_old_quote(self):
        self.seed();run=self.quote()
        self.choice.voice='fr-FR-Neural2-F';self.choice.revision+=1;self.choice.save()
        with self.assertRaises(Conflict):self.approve(run)
        self.assertFalse(CreditLedgerEntry.objects.exists())

    def test_sentence_audio_stays_openai_word_audio_uses_google(self):
        policy=word_audio.policy(self.dictionary)
        with patch.object(google_tts,'synthesize',return_value='google') as google, patch.object(tts,'synthesize',return_value='openai') as openai:
            self.assertEqual(word_audio.synthesize('four',dictionary=self.dictionary,expected=policy,speech_kind='entry',report={}), 'google')
            self.assertEqual(word_audio.synthesize('Le four est chaud.',dictionary=self.dictionary,expected=policy,speech_kind='sentence'), 'openai')
        self.assertEqual(google.call_args.kwargs['selected_voice'],'fr-FR-Wavenet-F')
        self.assertEqual(openai.call_count,1)

    def test_settings_requires_owner_admin_and_explicit_consent(self):
        url=reverse('community_dictionary:word-audio-settings',args=[self.dictionary.pk])
        with patch.object(google_tts,'check_access') as check:
            self.assertEqual(self.client.post(url,{'action':'save','voice':'fr-FR-Wavenet-F'}).status_code,409)
            self.assertEqual(self.client.post(url,{'action':'save','voice':'fr-FR-Neural2-F','consent':'on'}).status_code,302)
            self.assertEqual(check.call_count,1)
        self.choice.refresh_from_db();self.assertEqual(self.choice.voice,'fr-FR-Neural2-F')
        self.owner.is_staff=False;self.owner.save()
        self.seed()
        with self.assertRaises(Conflict):self.quote()
        self.assertEqual(self.client.post(url,{'action':'save','voice':''}).status_code,302)

    def test_batch_pages_and_preview_allow_nonhomographs(self):
        self.seed('fromage','cheese');run=self.quote()
        url=reverse('community_dictionary:audio-review-run',args=[self.dictionary.pk,run.pk])
        self.assertContains(self.client.get(url),'Google project charges')
        self.approve(run);self.finish(run)
        self.assertContains(self.client.get(url),'Use all usable replacements')
        item=run.items.get();clip=item.result['clips'][0]
        preview=reverse('community_dictionary:audio-review-preview',args=[self.dictionary.pk,run.pk,item.pk,clip['id']])
        self.assertEqual(self.client.get(preview).status_code,200)
        self.assertEqual(self.client.post(url,{'action':'accept_all'}).status_code,302)
        self.assertContains(self.client.get(url),'Replacement accepted')

    def test_all_listed_languages_can_quote_without_carrier_support(self):
        for language in ['German','Italian','Icelandic','Japanese','Spanish','Chinese','Slovak','English','Swedish']:
            with self.subTest(language=language):
                self.dictionary.language=language;self.dictionary.save()
                code=tts.language_code(language)
                self.choice.language=language;self.choice.voice=next(iter(google_tts.VOICES[code].values()));self.choice.save()
                self.seed('example-'+code, 'meaning')
                run=self.quote();self.approve(run)
                self.assertEqual(run.options['word_audio_policy']['voice'],self.choice.voice)
                porting.cancel(self.owner,run.pk)

    def test_policy_is_frozen_when_a_capture_is_created(self):
        from django.utils import timezone
        study=PictureCapture.objects.create(dictionary=self.dictionary,user=self.owner,expires_at=timezone.now())
        self.assertEqual(study.usage['word_audio_policy']['voice'],'fr-FR-Wavenet-F')


class GoogleFederationTests(SimpleTestCase):
    def test_explicit_aws_federation_configuration_and_rejection_of_other_sources(self):
        import json
        import tempfile
        from pathlib import Path
        info = {'type':'external_account',
            'audience':'//iam.googleapis.com/projects/123456/locations/global/workloadIdentityPools/clara-aws/providers/ec2',
            'subject_token_type':'urn:ietf:params:aws:token-type:aws4_request',
            'token_url':'https://sts.googleapis.com/v1/token',
            'service_account_impersonation_url':'https://iamcredentials.googleapis.com/v1/projects/-/serviceAccounts/clara-tts@community-dictionaries-tts.iam.gserviceaccount.com:generateAccessToken',
            'credential_source':{
                'environment_id':'aws1',
                'region_url':'http://169.254.169.254/latest/meta-data/placement/availability-zone',
                'url':'http://169.254.169.254/latest/meta-data/iam/security-credentials',
                'imdsv2_session_token_url':'http://169.254.169.254/latest/api/token',
                'regional_cred_verification_url':'https://sts.{region}.amazonaws.com?Action=GetCallerIdentity&Version=2011-06-15'}}
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'wif.json'; path.write_text(json.dumps(info))
            with override_settings(COMMUNITY_DICTIONARY_GOOGLE_TTS_ADC_FILE=str(path)):
                result = google_tts.credentials()
                self.assertEqual(result.quota_project_id,'community-dictionaries-tts')
                info['credential_source']['url']='https://untrusted.invalid/credentials'
                path.write_text(json.dumps(info))
                with self.assertRaises(Conflict):google_tts.credentials()

    def test_discovery_filters_language_and_known_pricing_families(self):
        from types import SimpleNamespace
        connection=Mock()
        connection.list_voices.return_value=SimpleNamespace(voices=[SimpleNamespace(name=n) for n in
            ['nl-NL-Wavenet-A','nl-NL-Neural2-A','fr-FR-Wavenet-F','nl-NL-Unknown-A']])
        user=SimpleNamespace(is_active=True,is_staff=True)
        with override_settings(COMMUNITY_DICTIONARY_GOOGLE_TTS_ENABLED=True), patch.object(google_tts,'client',return_value=connection):
            self.assertEqual(google_tts.discover(user,'Dutch'),['nl-NL-Wavenet-A','nl-NL-Neural2-A'])
        connection.synthesize_speech.assert_not_called()


from . import test_sentence_forms as form_fixtures, test_entry_media as media_fixtures


def google_recording(text, **kwargs):
    kwargs['before_request']()
    kwargs['report'].update(provider='google', model=kwargs['selected_voice'], voice=kwargs['selected_voice'],
        instructions_version=google_tts.VERSION, speech_cost_usd=str(google_tts.estimate(text,kwargs['method'])),
        attempts=[{'outcome':'usable'}])
    return (carrier_wave(), 'audio/wav', '.wav'), 3.2


@override_settings(COMMUNITY_DICTIONARY_GOOGLE_TTS_ENABLED=True, OPENAI_API_KEY='fixture-only', CREDITS_ENABLED=False)
class GoogleCaptureWorkflowTests(TestCase):
    url = form_fixtures.SentenceFormTests.url
    start = form_fixtures.SentenceFormTests.start
    action = form_fixtures.SentenceFormTests.action
    ready = form_fixtures.SentenceFormTests.ready
    publish = form_fixtures.SentenceFormTests.publish
    generated = form_fixtures.SentenceFormTests.generated
    complete_audio = form_fixtures.SentenceFormTests.complete_audio
    approve = form_fixtures.SentenceFormTests.approve
    run_batch = form_fixtures.SentenceFormTests.run_batch

    def setUp(self):
        form_fixtures.SentenceFormTests.setUp(self)
        self.owner.is_staff=True;self.owner.save()
        DictionaryWordAudioSettings.objects.create(dictionary=self.d,language='Swedish',
            authorised_by=self.owner,voice='sv-SE-Wavenet-F')

    def test_picture_workflow_generates_google_words_and_forms_openai_sentence(self):
        with patch.object(google_tts,'synthesize',side_effect=google_recording) as google:
            study,entry=self.generated();self.complete_audio(study)
        self.assertEqual(google.call_count,7)
        self.assertEqual(self.tts.call_count,1)
        form=entry.contributions.get(kind='form',word='ligger')
        self.assertEqual(sf.audio(form).provenance['voice'],'sv-SE-Wavenet-F')
        self.assertEqual(sf.audio(form).provenance['provider'],'google')
        self.assertTrue(all(c.status=='ready' for c in study.speech.all()))

    def test_missing_form_tool_honours_google_policy_and_character_estimate(self):
        from community_dictionary import form_jobs
        study,entry=self.generated()
        run=self.approve(form_jobs.quote(self.owner,self.d,uuid.uuid4()))
        self.assertEqual(run.options['word_audio_policy']['voice'],'sv-SE-Wavenet-F')
        self.assertLess(run.estimated_usd,.001)
        with patch.object(google_tts,'synthesize',side_effect=google_recording) as google:
            self.run_batch(run)
        self.assertEqual(google.call_count,3)
        self.assertEqual(run.speech.filter(status='ready').count(),3)


@override_settings(COMMUNITY_DICTIONARY_GOOGLE_TTS_ENABLED=True, OPENAI_API_KEY='fixture-only', CREDITS_ENABLED=False)
class GoogleIndividualAudioTests(TestCase):
    url=media_fixtures.EntryMediaTests.url
    generate=media_fixtures.EntryMediaTests.generate
    audio_study=media_fixtures.EntryMediaTests.audio_study
    audio_save=media_fixtures.EntryMediaTests.audio_save

    def setUp(self):
        media_fixtures.EntryMediaTests.setUp(self)
        self.owner.is_staff=True;self.owner.save()
        DictionaryWordAudioSettings.objects.create(dictionary=self.dictionary,language='Swedish',
            authorised_by=self.owner,voice='sv-SE-Wavenet-F')

    def test_word_page_preview_save_and_credit_metadata(self):
        with patch.object(google_tts,'synthesize',side_effect=google_recording) as google:
            study=self.audio_study()
        self.assertEqual(study.status,'ready');self.assertEqual(google.call_count,1)
        self.assertEqual(self.audio_save(study).status_code,302)
        audio=self.entry.contributions.get(kind='audio',status='accepted')
        self.assertEqual(audio.provenance['provider'],'google')
        self.assertEqual(audio.provenance['voice'],'sv-SE-Wavenet-F')
        self.assertEqual(AIUsageCharge.objects.get(operation='community_tts').provider,'google')
