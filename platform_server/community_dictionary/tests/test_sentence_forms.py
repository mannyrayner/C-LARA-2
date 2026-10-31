import copy
import json
import uuid
from decimal import Decimal
from unittest.mock import Mock, patch
from django.test import TestCase, override_settings, Client
from django.urls import reverse
from community_dictionary import capture, capture_ai, sentence_forms as sf, form_jobs, porting, port_tasks
from community_dictionary import port_vocabulary_tasks as jobs
from community_dictionary.models import Contribution, Entry, SentenceWord, PortSpeech, CaptureSpeech
from community_dictionary.services import Conflict, add_contributions
from community_dictionary.participation import withdraw_all, restore_all
from community_dictionary.lexicon import recordings
from projects.models import CreditAccount, CreditLedgerEntry
from . import test_picture_capture as fixtures
from .test_picture_capture import response, RESULT, speech
from . import test_tts_guidance as guidance_fixtures


@override_settings(OPENAI_API_KEY='fixture-only', CREDITS_ENABLED=False,
    COMMUNITY_DICTIONARY_PORT_WINDOW=2, PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class SentenceFormTests(TestCase):
    setUp = fixtures.PictureCaptureTests.setUp
    url = fixtures.PictureCaptureTests.url
    start = fixtures.PictureCaptureTests.start
    action = fixtures.PictureCaptureTests.action
    ready = fixtures.PictureCaptureTests.ready
    publish = fixtures.PictureCaptureTests.publish

    def generated(self, data=None):
        data = copy.deepcopy(data or RESULT)
        for word in data['words']:
            word['form_meaning'] = {'Katten':'the cat','ligger':'is lying','på':'on','soffan':'the sofa'}.get(word['surface'], 'contextual meaning')
        self.ai.return_value = response(data)
        study = self.ready(); entry = self.publish(study)
        return study, entry

    def complete_audio(self, study):
        capture.run_audio(str(study.pk))

    def approve(self, run):
        with patch('community_dictionary.port_tasks.send'), patch.object(jobs, 'send_speech'), self.captureOnCommitCallbacks(execute=True):
            porting.approve(self.owner, run.pk)
        run.refresh_from_db()
        return run

    def run_batch(self, run, fail_audio=False):
        def analyse(entry, rows, **kwargs):
            return response({'forms':[{'id':link.pk, 'surface':link.surface or 'Katten',
                'form_meaning':'context translation'} for link,part in rows if part is None]})
        with patch.object(form_jobs, 'analyse', side_effect=analyse) as api, \
             patch('community_dictionary.port_tasks.send'), patch.object(jobs,'send_speech'), \
             self.captureOnCommitCallbacks(execute=True):
            while run.items.filter(status='queued').exists():
                for item in run.items.filter(status='queued'):
                    form_jobs.process(item.pk)
                port_tasks.dispatch(str(run.pk))
            while run.speech.filter(status='queued').exists():
                for clip in run.speech.filter(status='queued'):
                    with patch('community_dictionary.tts.synthesize', side_effect=TimeoutError if fail_audio else speech):
                        jobs.speak(clip.pk)
                port_tasks.dispatch(str(run.pk))
        run.refresh_from_db()
        return api

    def test_capture_keeps_shared_lemmas_and_adds_context_audio(self):
        study, entry = self.generated()
        self.assertEqual(Entry.objects.filter(entry_type='word').count(),4)
        self.assertEqual(entry.contributions.filter(kind='form').count(),3)
        self.assertEqual(study.speech.filter(kind='form').count(),3)
        self.complete_audio(study)
        self.assertEqual(len(recordings(entry,self.d)),1)  # no form audio masquerades as sentence
        form = entry.contributions.get(kind='form',word='ligger')
        self.assertEqual(form.meaning,'is lying')
        self.assertEqual(sf.audio(form).provenance['source_text'],'ligger')
        self.assertEqual(self.tts.call_count,8)  # four lemmas, sentence, three different forms
        self.assertEqual([c.kwargs['speech_kind'] for c in self.tts.call_args_list if c.args[0]=='ligger'],['entry'])
        second = self.generated()[1]
        self.assertEqual(Entry.objects.filter(entry_type='word').count(),4)
        self.assertNotEqual(sf.find(sf.links(entry).get(surface='ligger')).pk,
                            sf.find(sf.links(second).get(surface='ligger')).pk)

    def test_discontinuous_mwe_uses_sentence_recording(self):
        data = {'outcome':'ready','feedback':'Confirm?', 'sentence':'Der Mann zieht seine Jacke an.',
            'translation':'The man puts on his jacket.', 'words':[
                {'lemma':'anziehen','meaning':'put on','surface':'zieht … an','existing_id':0}]}
        study, entry = self.generated(data); self.complete_audio(study)
        self.assertFalse(study.speech.filter(kind='form').exists())
        row = sf.presentation(sf.links(entry).get())
        self.assertTrue(row['in_sentence'])
        self.assertEqual(row['audio'].provenance['source_text'], data['sentence'])

    def test_member_and_public_forms_and_exact_revision_guards(self):
        study, entry = self.generated(); self.complete_audio(study)
        page = self.client.get(self.url('entry',entry.pk))
        self.assertContains(page,'is lying'); self.assertContains(page,'Dictionary form')
        self.d.public_browsing_enabled=True; self.d.save()
        visitor = Client()
        self.assertContains(visitor.get(self.url('public-entry',entry.pk)), 'is lying')
        part = entry.contributions.get(kind='form',word='ligger'); audio = sf.audio(part)
        playable = visitor.get(self.url('public-media', audio.pk)); self.assertEqual(playable.status_code,200); playable.close()
        add_contributions(entry,self.owner,{'word':'Katten sitter.'},[],publish=True)
        part.entry.refresh_from_db()
        self.assertIsNone(sf.current(part))
        self.assertEqual(visitor.get(self.url('public-media',audio.pk)).status_code,404)

    def test_withdraw_restore_retains_private_forms_and_audio(self):
        study, entry = self.generated(); self.complete_audio(study)
        part = entry.contributions.get(kind='form',word='ligger'); clip = sf.audio(part)
        state = withdraw_all(self.user,self.d.pk,0)
        part.refresh_from_db(); clip.refresh_from_db()
        self.assertTrue(part.entry.dictionary.personal)
        self.assertTrue(clip.entry.dictionary.personal)
        restore_all(self.user,self.d.pk,1)
        part.refresh_from_db()
        self.assertIsNotNone(sf.current(part)); self.assertEqual(sf.audio(part).pk,clip.pk)

    def test_backfill_quote_approval_idempotency_and_incremental_skip(self):
        study=self.ready(); entry=self.publish(study)
        with patch.object(form_jobs,'analyse') as api:
            run=form_jobs.quote(self.owner,self.d,uuid.uuid4())
            self.assertEqual(run.items.count(),1); api.assert_not_called()
            self.assertFalse(run.approved_at)
            self.assertEqual(form_jobs.quote(self.owner,self.d,run.pk).pk,run.pk)
        self.approve(run); self.run_batch(run)
        self.assertTrue(run.settled); self.assertEqual(run.status,'complete')
        self.assertEqual(run.speech.filter(status='ready').count(),3)
        self.assertFalse(form_jobs.quote(self.owner,self.d,uuid.uuid4()).items.exists())
        count=Contribution.objects.count(); self.run_batch(run); self.assertEqual(Contribution.objects.count(),count)

    def test_failed_audio_retry_keeps_text_and_only_requests_missing_audio(self):
        self.publish(self.ready())
        run=self.approve(form_jobs.quote(self.owner,self.d,uuid.uuid4()))
        self.run_batch(run,fail_audio=True)
        self.assertTrue(run.settled); self.assertEqual(run.speech.filter(status='failed').count(),3)
        count=Contribution.objects.filter(kind='form').count()
        retry=self.approve(form_jobs.quote(self.owner,self.d,uuid.uuid4()))
        api=self.run_batch(retry); api.assert_not_called()
        self.assertEqual(Contribution.objects.filter(kind='form').count(),count)
        self.assertEqual(retry.speech.filter(status='ready').count(),3)

    def test_human_correction_preserved_by_backfill(self):
        study,entry=self.generated()
        part=entry.contributions.get(kind='form',word='ligger'); link=sf.current(part)
        changed=sf.publish(link,'lies',self.owner,{'origin':'human'},replace=part.pk)
        run=self.approve(form_jobs.quote(self.owner,self.d,uuid.uuid4()))
        api=self.run_batch(run); api.assert_not_called()
        self.assertEqual(sf.find(link).pk,changed.pk)
        self.assertEqual(changed.controlled_by_id,self.user.pk)
        self.assertEqual(sf.audio(changed).provenance['source_text'],'ligger')

    def test_sentence_edit_before_publication_discards_inflight_result(self):
        entry=self.publish(self.ready()); run=self.approve(form_jobs.quote(self.owner,self.d,uuid.uuid4()))
        def change(entry,rows,**kwargs):
            add_contributions(entry,self.owner,{'word':'Katten sitter.'},[],publish=True)
            return response({'forms':[{'id':l.pk,'surface':l.surface,'form_meaning':'x'} for l,p in rows]})
        with patch.object(form_jobs,'analyse',side_effect=change), patch('community_dictionary.port_tasks.send'):
            form_jobs.process(run.items.get().pk)
        self.assertFalse(Contribution.objects.filter(kind='form').exists())
        self.assertEqual(run.items.get().status,'discarded')

    def test_source_word_edit_invalidates_form_without_changing_sentence(self):
        study,entry=self.generated(); part=entry.contributions.get(kind='form',word='ligger')
        target=sf.current(part).word_entry
        add_contributions(target,self.owner,{'meaning':'be situated'},[],publish=True)
        self.assertIsNone(sf.current(part))

    def test_owner_only_quotes_and_editor_only_correction(self):
        study,entry=self.generated(); part=entry.contributions.get(kind='form',word='ligger')
        self.assertEqual(self.client.get(self.url('forms-start')).status_code,404)
        self.assertEqual(self.client.get(self.url('form-edit',part.pk)).status_code,404)
        self.client.force_login(self.owner)
        self.assertContains(self.client.get(self.url('forms-start')),'Estimate missing work')
        run=form_jobs.quote(self.owner,self.d,uuid.uuid4())
        self.assertContains(self.client.get(self.url('forms-run',run.pk)),'Rough API estimate')
        self.assertEqual(self.client.post(self.url('forms-run',run.pk),{'action':'approve'}).status_code,409)
        self.assertEqual(self.client.post(self.url('form-edit',part.pk),{'meaning':'lies','revision':part.pk}).status_code,302)

    @override_settings(CREDITS_ENABLED=True)
    def test_credit_shortfall_and_once_only_reservation_refund(self):
        CreditAccount.objects.update_or_create(user=self.user,defaults={'balance_usd':Decimal('10')})
        self.publish(self.ready()); run=form_jobs.quote(self.owner,self.d,uuid.uuid4())
        CreditAccount.objects.update_or_create(user=self.owner,defaults={'balance_usd':Decimal('0')})
        with self.assertRaises(Conflict): self.approve(run)
        CreditAccount.objects.filter(user=self.owner).update(balance_usd=Decimal('10'))
        self.approve(run); self.approve(run)
        self.assertEqual(CreditLedgerEntry.objects.filter(user=self.owner,metadata__kind='reservation').count(),1)
        self.run_batch(run)
        account=CreditAccount.objects.get(user=self.owner)
        self.assertEqual(account.balance_usd,Decimal('10')-run.charged_usd)
        port_tasks.dispatch(str(run.pk));account.refresh_from_db()
        self.assertEqual(account.balance_usd,Decimal('10')-run.charged_usd)

    def test_budget_pause_makes_no_request_and_cancel_keeps_content(self):
        entry=self.publish(self.ready()); run=form_jobs.quote(self.owner,self.d,uuid.uuid4())
        run.items.update(allowance_usd=Decimal('0'))
        run.allowance_usd=Decimal('0');run.save(update_fields=['allowance_usd'])
        self.approve(run)
        with patch.object(form_jobs,'analyse') as api, patch('community_dictionary.port_tasks.send'):
            form_jobs.process(run.items.get().pk)
        api.assert_not_called()
        self.assertEqual(run.items.get().status,'budget')
        porting.cancel(self.owner,run.pk);run.refresh_from_db()
        self.assertTrue(run.settled)
        self.assertEqual(entry.word,RESULT['sentence'])

    def test_missing_surface_uses_alignment_and_keeps_lemma(self):
        entry=self.publish(self.ready())
        link=sf.links(entry).get(surface='Katten');link.surface='';link.save(update_fields=['surface'])
        run=self.approve(form_jobs.quote(self.owner,self.d,uuid.uuid4()))
        self.run_batch(run)
        link.refresh_from_db()
        self.assertEqual(link.surface,'Katten')
        self.assertEqual(link.word_entry.word,'katt')
        self.assertIsNotNone(sf.find(link))

    def test_schema_and_context_translation_validation(self):
        data=copy.deepcopy(RESULT)
        for w in data['words']: w['form_meaning']='context'
        self.assertEqual(capture_ai.parse(response(data)),data)
        data['words'][0]['form_meaning']=[]
        with self.assertRaises(ValueError): capture_ai.parse(response(data))

    def test_refresh_distinguishes_saved_forms_from_finished_recordings(self):
        self.generated()
        run=self.approve(form_jobs.quote(self.owner,self.d,uuid.uuid4()))
        self.client.force_login(self.owner)
        page=self.client.get(self.url('forms-run',run.pk))
        self.assertContains(page,'Sentences finished, including audio: 0 / 1')
        self.assertEqual(page.context['progress']['text_ready'],0)
        self.assertIn('no-store',page['Cache-Control'])
        with patch('community_dictionary.port_tasks.send'),patch.object(jobs,'send_speech'):
            form_jobs.process(run.items.get().pk)
        page=self.client.get(self.url('forms-run',run.pk))
        self.assertEqual(page.context['progress']['text_ready'],1)
        self.assertEqual(page.context['progress']['audio_pending'],3)
        self.assertEqual(page.context['progress']['complete'],0)
        clips=list(run.speech.order_by('pk'))
        PortSpeech.objects.filter(pk=clips[0].pk).update(status='ready')
        PortSpeech.objects.filter(pk=clips[1].pk).update(status='failed')
        PortSpeech.objects.filter(pk=clips[2].pk).update(status='budget')
        page=self.client.get(self.url('forms-run',run.pk))
        p=page.context['progress']
        self.assertEqual((p['audio_ready'],p['audio_failed'],p['audio_pending'],p['complete']),(1,1,1,0))
        self.assertEqual(p['failed'],1)
        run.speech.update(status='ready')
        page=self.client.get(self.url('forms-run',run.pk))
        self.assertContains(page,'Sentences finished, including audio: 1 / 1')
        self.assertEqual(page.context['progress']['audio_ready'],3)

    def test_progress_reads_are_bounded_and_hide_private_or_changed_sources(self):
        for _ in range(3):self.generated()
        run=form_jobs.quote(self.owner,self.d,uuid.uuid4())
        with self.assertNumQueries(2):
            rows,progress=form_jobs.progress_rows(run,self.d)
        self.assertEqual(progress['total'],3)
        self.assertTrue(all(row['entry'] for row in rows))
        first=run.items.first()
        Entry.objects.filter(pk=first.source_entry_id).update(archived=True)
        rows,_=form_jobs.progress_rows(run,self.d)
        self.assertIsNone(next(row['entry'] for row in rows if row['item'].pk==first.pk))
        from community_dictionary.models import Dictionary
        private=Dictionary.objects.create(owner=self.outsider,name='Private',language='French',personal=True)
        other=run.items.exclude(pk=first.pk).first()
        Entry.objects.filter(pk=other.source_entry_id).update(dictionary=private)
        rows,_=form_jobs.progress_rows(run,self.d)
        self.assertIsNone(next(row['entry'] for row in rows if row['item'].pk==other.pk))
        Entry.objects.filter(pk=first.source_entry_id).update(archived=False)
        add_contributions(first.source_entry,self.owner,{'word':'Changed wording.'},[],publish=True)
        rows,_=form_jobs.progress_rows(run,self.d)
        self.assertIsNone(next(row['entry'] for row in rows if row['item'].pk==first.pk))

    def french_form(self):
        self.d.language='French';self.d.save()
        data={'outcome':'ready','feedback':'Confirm?', 'sentence':'La fille pose un livre.',
              'translation':'The girl puts down a book.', 'words':[
                  {'lemma':'poser','meaning':'put down','surface':'pose','existing_id':0}]}
        study,entry=self.generated(data)
        return study,entry,entry.contributions.get(kind='form',word='pose')

    def check_french_coach(self, coach, spoken, part):
        request=json.loads(coach.call_args.kwargs['input'])
        self.assertEqual(request['word'],'pose')
        self.assertEqual(request['target_language'],'fr')
        self.assertEqual(request['meaning'],part.meaning)
        self.assertEqual(request['meaning_language'],'English')
        self.assertEqual(spoken.call_args.kwargs['input'],'pose')
        self.assertIn('/poz/',spoken.call_args.kwargs['instructions'])
        audio=sf.audio(part)
        self.assertEqual(audio.provenance['synthesis']['english_homographs'],['pose'])
        self.assertEqual(str(sf.audio_details(audio)['audio_method']),
                         'Pronunciation guidance for English homographs')

    def test_capture_form_homograph_uses_actual_french_guidance_adapter(self):
        study,entry,part=self.french_form()
        clip=study.speech.get(kind='form')
        patch.stopall()  # Only mock the provider below, not tts.synthesize.
        coach=Mock(return_value=guidance_fixtures.guidance(ipa='poz',definition='met un objet quelque part'))
        with guidance_fixtures.provider(coaching=coach) as (coach,spoken,_):
            capture.speak(clip.pk)
        self.check_french_coach(coach,spoken,part)

    def test_backfill_form_homograph_uses_actual_french_guidance_adapter(self):
        study,entry,part=self.french_form()
        run=self.approve(form_jobs.quote(self.owner,self.d,uuid.uuid4()))
        with patch('community_dictionary.port_tasks.send'),patch.object(jobs,'send_speech'):
            form_jobs.process(run.items.get().pk)
        clip=run.speech.get()
        patch.stopall()
        coach=Mock(return_value=guidance_fixtures.guidance(ipa='poz',definition='met un objet quelque part'))
        with guidance_fixtures.provider(coaching=coach) as (coach,spoken,_),patch.object(jobs,'send_speech'):
            jobs.speak(clip.pk)
        self.check_french_coach(coach,spoken,part)
        self.client.force_login(self.owner)
        self.assertContains(self.client.get(self.url('entry',entry.pk)),
                            'Pronunciation guidance for English homographs')
        self.d.public_browsing_enabled=True;self.d.save()
        self.assertNotContains(Client().get(self.url('public-entry',entry.pk)),'Audio method:')

    def test_audio_method_does_not_claim_unrecorded_guidance_or_extraction(self):
        source=Mock(provenance={})
        self.assertEqual(str(sf.audio_details(source)['audio_method']),'Audio method not recorded')
        source.provenance={'synthesis':{'instructions':'French instructions','english_homographs':['pose']}}
        self.assertEqual(str(sf.audio_details(source)['audio_method']),'Direct speech with language instructions')
        source.provenance={'synthesis':{'strategy':'mwe_carrier'}}
        self.assertEqual(str(sf.audio_details(source)['audio_method']),'Carrier phrase with audio extraction')
        self.assertEqual(str(sf.audio_details(source,in_sentence=True)['audio_method']),'Whole-sentence recording')


from . import test_guided as guided_fixtures, test_port_vocabulary as port_fixtures


@override_settings(OPENAI_API_KEY='fixture-only', CREDITS_ENABLED=False,
    PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class GuidedFormTests(TestCase):
    setUp = guided_fixtures.GuidedTests.setUp
    choose = guided_fixtures.GuidedTests.choose
    start = guided_fixtures.GuidedTests.start
    action = guided_fixtures.GuidedTests.action
    described = guided_fixtures.GuidedTests.described
    published = guided_fixtures.GuidedTests.published
    url = fixtures.PictureCaptureTests.url
    word = fixtures.PictureCaptureTests.word

    def test_guided_worker_generates_forms_and_failed_form_retry_is_visible(self):
        data=copy.deepcopy(RESULT)
        for word in data['words']: word['form_meaning']='context gloss'
        self.ai.return_value=response(data)
        def generate(text,**kw):
            if text=='ligger': raise TimeoutError
            return speech(text,**kw)
        self.tts.side_effect=generate
        study=self.published()
        failed=study.speech.get(kind='form',text='ligger')
        self.assertEqual(failed.status,'failed')
        self.assertEqual([c.pk for c in capture.failed_audio(study)],[failed.pk])
        self.assertContains(self.client.get(self.url('guided-detail',study.pk)), 'context gloss')
        self.tts.side_effect=speech
        from community_dictionary import writing, guided
        writing.retry_audio(study.pk,self.user); guided.run(study.pk)
        self.assertFalse(capture.failed_audio(study))
        self.assertEqual(study.speech.filter(kind='form',text='ligger',status='ready').count(),1)


@override_settings(OPENAI_API_KEY='fixture-only', CREDITS_ENABLED=False,
    COMMUNITY_DICTIONARY_PORT_WINDOW=2, PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class PortFormTests(TestCase):
    start=fixtures.PictureCaptureTests.start
    action=fixtures.PictureCaptureTests.action
    ready=fixtures.PictureCaptureTests.ready
    publish=fixtures.PictureCaptureTests.publish
    setUp=port_fixtures.PortVocabularyTests.setUp
    sentence=port_fixtures.PortVocabularyTests.sentence
    quote=port_fixtures.PortVocabularyTests.quote
    approve=port_fixtures.PortVocabularyTests.approve
    process=port_fixtures.PortVocabularyTests.process
    save=port_fixtures.PortVocabularyTests.save
    translated=port_fixtures.PortVocabularyTests.translated
    stage_two=port_fixtures.PortVocabularyTests.stage_two
    analyse=port_fixtures.PortVocabularyTests.analyse
    accept_words=port_fixtures.PortVocabularyTests.accept_words
    finish_audio=port_fixtures.PortVocabularyTests.finish_audio
    url=fixtures.PictureCaptureTests.url

    def test_language_port_uses_target_sentence_forms_and_shared_audio_queue(self):
        first,entry=self.translated()
        run=self.stage_two(first.port);item=run.items.get()
        words=copy.deepcopy(port_fixtures.WORDS)
        words[0]['form_meaning']='rests'
        words[1]['form_meaning']='fabric'
        self.analyse(item,words);self.accept_words(item,words);self.finish_audio(run)
        part=entry.contributions.get(kind='form')
        self.assertEqual((part.word,part.meaning),('repose','rests'))
        self.assertIsNotNone(sf.audio(part))
        self.assertEqual(run.speech.filter(status='ready').count(),3)
