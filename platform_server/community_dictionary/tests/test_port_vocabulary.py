"""Sentence-first ports: fixed inputs, shared senses, paid jobs and old-port repair."""
import json
import uuid
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch
from django.test import TestCase, override_settings
from django.urls import reverse
from community_dictionary import capture, porting, port_tasks, port_vocabulary as vocab, port_vocabulary_tasks as jobs, port_vocabulary_ai
from community_dictionary.models import Entry, Contribution, SentenceWord, PortRun, PortSpeech, VocabularyState, LanguageCheck
from community_dictionary.services import add_contributions, Conflict
from community_dictionary.participation import withdraw_all, restore_all
from projects.models import CreditAccount, CreditLedgerEntry, AIUsageCharge
from . import test_sentence_porting as legacy_tests
from . import test_porting as port_tests
from .test_porting import response, speech
from . import test_picture_capture as capture_tests

SENTENCE='Un bijou brillant en forme de lapin repose sur du tissu.'
WORDS=[{'lemma':'reposer','meaning':'rest','surface':'repose','existing_id':0},
       {'lemma':'tissu','meaning':'fabric','surface':'tissu','existing_id':0}]

@override_settings(OPENAI_API_KEY='fixture-only', CREDITS_ENABLED=False,
    COMMUNITY_DICTIONARY_PORT_WINDOW=2, PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class PortVocabularyTests(TestCase):
    setUp=legacy_tests.SentencePortingTests.setUp
    start=capture_tests.PictureCaptureTests.start
    action=capture_tests.PictureCaptureTests.action
    ready=capture_tests.PictureCaptureTests.ready
    publish=capture_tests.PictureCaptureTests.publish
    url=capture_tests.PictureCaptureTests.url
    sentence=legacy_tests.SentencePortingTests.sentence
    approve=port_tests.PortingTests.approve
    process=port_tests.PortingTests.process
    save=port_tests.PortingTests.save
    quote=port_tests.PortingTests.quote

    def translated(self, text=SENTENCE):
        source=self.sentence()
        run=self.approve(self.quote(language='French'),balance='100')
        self.assertEqual(run.items.count(),1)
        item=run.items.get()
        self.process(item,response(word=text,meaning=source.meaning,category=''))
        entry=self.save(item)
        return run,entry

    def stage_two(self,port):
        run=vocab.quote(self.owner,port,uuid.uuid4())
        return self.approve(run,balance='100')

    def analyse(self,item,words=None):
        result=SimpleNamespace(status='completed',output_text=json.dumps({'words':WORDS if words is None else words}),
            usage=SimpleNamespace(input_tokens=1000,output_tokens=100))
        with patch.object(port_vocabulary_ai,'analyse',return_value=result) as api, \
             patch('community_dictionary.port_tasks.send'),self.captureOnCommitCallbacks(execute=True):
            jobs.process_item(item.pk)
        item.refresh_from_db()
        self.assertEqual(item.status,'ready',item.message)
        return api

    def accept_words(self,item,words=None):
        with patch.object(jobs,'send_speech'),patch('community_dictionary.port_tasks.send'),self.captureOnCommitCallbacks(execute=True):
            entry=vocab.save_item(self.owner,item.pk,WORDS if words is None else words)
        item.refresh_from_db()
        return entry

    def finish_audio(self,run):
        with patch('community_dictionary.tts.synthesize',side_effect=speech) as synth, \
             patch.object(jobs,'send_speech'),patch('community_dictionary.port_tasks.send'),self.captureOnCommitCallbacks(execute=True):
            while run.speech.filter(status='queued').exists():
                for clip in list(run.speech.filter(status='queued')):
                    jobs.speak(clip.pk)
        run.refresh_from_db()
        return synth

    def test_new_translation_ignores_source_word_pages_and_keeps_sentence_audio(self):
        run,entry=self.translated()
        self.assertEqual(run.stage,'sentences')
        self.assertEqual(entry.word,SENTENCE)
        self.assertFalse(run.port.destination.entries.filter(entry_type='word').exists())
        self.assertTrue(entry.contributions.filter(kind='audio',status='accepted').exists())
        self.assertTrue(vocab.pending(entry))
        self.assertEqual(self.quote(language='French',port=run.port).items.count(),0)
        page=self.client.get(reverse('community_dictionary:entry',args=[entry.dictionary_id,entry.pk]))
        self.assertContains(page,'Vocabulary needs updating')

    def test_stage_two_uses_final_edited_sentence_and_picture_without_retranslation(self):
        first,entry=self.translated()
        add_contributions(entry,self.owner,{'word':SENTENCE.replace('brillant','doré'),'edit_text':True},[],publish=True)
        entry.refresh_from_db()
        with patch('community_dictionary.port_ai.translate') as translator:
            run=self.stage_two(first.port);item=run.items.get();api=self.analyse(item)
            self.assertFalse(translator.called)
        self.assertEqual(api.call_args.args[0]['sentence'],entry.word)
        self.assertIsInstance(api.call_args.args[1],bytes)
        self.accept_words(item);self.finish_audio(run)
        entry.refresh_from_db()
        self.assertTrue(vocab.current_state(entry))
        self.assertEqual(set(capture.sentence_links(entry.dictionary).values_list('word_entry__word',flat=True)),{'reposer','tissu'})
        self.assertEqual(vocab.quote(self.owner,first.port,uuid.uuid4()).items.count(),0)

    def test_contextual_review_editing_add_remove_and_bulk_accept_are_available(self):
        first,entry=self.translated();run=self.stage_two(first.port);item=run.items.get();self.analyse(item)
        url=reverse('community_dictionary:port-review',args=[self.d.pk,run.pk,item.pk])
        page=self.client.get(url)
        self.assertContains(page,SENTENCE);self.assertContains(page,'Picture for the accepted sentence')
        self.assertContains(page,'words-0-lemma');self.assertContains(page,'capture.js')
        media=self.client.get(reverse('community_dictionary:port-media',args=[self.d.pk,run.pk,item.pk,'image']))
        self.assertEqual(media.status_code,200);media.close()
        progress=self.client.get(reverse('community_dictionary:port-run',args=[self.d.pk,run.pk]))
        self.assertContains(progress,'Accept all remaining suggestions')
        with patch.object(jobs,'send_speech'), self.captureOnCommitCallbacks(execute=True):
            saved=self.client.post(url,{'words-TOTAL_FORMS':'3','words-INITIAL_FORMS':'2',
                'words-0-lemma':'reposer','words-0-meaning':'rest','words-0-surface':'repose',
                'words-1-lemma':'tissu','words-1-meaning':'fabric','words-1-DELETE':'on',
                'words-2-lemma':'bijou','words-2-meaning':'jewel','words-2-surface':'bijou','action':'save'})
        self.assertEqual(saved.status_code,302)
        self.assertEqual(set(entry.dictionary.entries.filter(entry_type='word').values_list('word',flat=True)),{'reposer','bijou'})

    def test_shared_lemma_and_sense_have_one_page_and_one_audio_job(self):
        first,entry=self.translated()
        second=Entry.objects.create(dictionary=entry.dictionary,created_by=self.owner,entry_type='sentence')
        add_contributions(second,self.owner,{'word':'Le chat repose sur du tissu.','meaning':'The cat rests on fabric.'},[],publish=True)
        run=self.stage_two(first.port)
        for item in run.items.all():self.analyse(item)
        with patch.object(jobs,'send_speech'),self.captureOnCommitCallbacks(execute=True):
            self.assertEqual(porting.accept_remaining(self.owner,run.pk),(2,0))
        self.assertEqual(entry.dictionary.entries.filter(entry_type='word').count(),2)
        self.assertEqual(run.speech.count(),2)
        self.assertEqual(SentenceWord.objects.filter(word_entry__dictionary=entry.dictionary).count(),4)
        synth=self.finish_audio(run);self.assertEqual(synth.call_count,2)
        self.assertEqual(run.status,'complete');self.assertTrue(run.settled)
        with patch('community_dictionary.tts.synthesize') as again:
            for clip in run.speech.all():jobs.speak(clip.pk)
            self.assertEqual(porting.accept_remaining(self.owner,run.pk),(0,0))
            self.assertFalse(again.called)
        self.assertFalse(LanguageCheck.objects.filter(entry__dictionary=entry.dictionary).exists())

    def test_same_lemma_different_sense_is_not_merged(self):
        first,entry=self.translated()
        existing=Entry.objects.create(dictionary=entry.dictionary,created_by=self.owner)
        add_contributions(existing,self.owner,{'word':'reposer','meaning':'put back'},[],publish=True)
        run=self.stage_two(first.port);item=run.items.get();self.analyse(item);self.accept_words(item)
        self.assertEqual(entry.dictionary.entries.filter(word='reposer').count(),2)
        self.assertEqual(SentenceWord.objects.get(sentence_text=entry.current_text,word_entry__word='reposer').word_entry.meaning,'rest')

    def test_changed_sentence_or_word_revision_requires_refresh(self):
        first,entry=self.translated();run=self.stage_two(first.port);item=run.items.get();self.analyse(item)
        self.accept_words(item);self.finish_audio(run)
        word=entry.dictionary.entries.get(word='reposer')
        add_contributions(word,self.owner,{'meaning':'rest upon something','edit_text':True},[],publish=True)
        self.assertTrue(vocab.pending(entry))
        next_run=self.stage_two(first.port);next_item=next_run.items.get();self.analyse(next_item)
        add_contributions(entry,self.owner,{'word':'Un bijou repose ici.','edit_text':True},[],publish=True)
        with self.assertRaises(Conflict):self.accept_words(next_item)
        self.assertEqual(porting.accept_remaining(self.owner,next_run.pk),(0,1))

    def test_bulk_accept_stage_one_skips_flags_and_stage_two_skips_flags(self):
        source=self.sentence();run=self.approve(self.quote(language='French'));item=run.items.get()
        self.process(item,response(word=SENTENCE,meaning=source.meaning,category=''))
        item.needs_attention=True;item.save(update_fields=['needs_attention'])
        self.assertEqual(porting.accept_remaining(self.owner,run.pk),(0,0))
        item.needs_attention=False;item.save(update_fields=['needs_attention'])
        self.assertEqual(porting.accept_remaining(self.owner,run.pk),(1,0))
        second=self.stage_two(run.port);candidate=second.items.get();self.analyse(candidate)
        candidate.needs_attention=True;candidate.save(update_fields=['needs_attention'])
        self.assertEqual(porting.accept_remaining(self.owner,second.pk),(0,0))
        url=reverse('community_dictionary:port-action',args=[self.d.pk,second.pk])
        self.assertEqual(self.client.post(url,{'action':'accept-all'}).status_code,400)

    @override_settings(CREDITS_ENABLED=True)
    def test_estimate_approval_reservation_review_audio_and_refund(self):
        with override_settings(CREDITS_ENABLED=False):
            first,entry=self.translated()
        run=vocab.quote(self.owner,first.port,uuid.uuid4())
        self.assertEqual(run.status,'estimate');self.assertFalse(run.speech.exists())
        CreditAccount.objects.filter(user=self.owner).update(balance_usd=0)
        with self.assertRaises(Conflict):porting.approve(self.owner,run.pk)
        run=self.approve(run,balance='100');item=run.items.get();self.analyse(item)
        run.refresh_from_db();self.assertFalse(run.settled)
        self.accept_words(item);run.refresh_from_db();self.assertFalse(run.settled)
        self.finish_audio(run)
        self.assertTrue(run.settled);self.assertLess(run.charged_usd,run.reserved_usd)
        self.assertEqual(CreditAccount.objects.get(user=self.owner).balance_usd,Decimal(100)-run.charged_usd)
        self.assertEqual(AIUsageCharge.objects.filter(request_type__startswith=f'port:{item.pk}:audio:').count(),2)

    def test_cancel_stops_queued_audio_and_keeps_accepted_words(self):
        first,entry=self.translated();run=self.stage_two(first.port);item=run.items.get();self.analyse(item);self.accept_words(item)
        porting.cancel(self.owner,run.pk)
        with patch('community_dictionary.tts.synthesize') as api:
            for clip in run.speech.all():jobs.speak(clip.pk)
            self.assertFalse(api.called)
        run.refresh_from_db();self.assertTrue(run.settled)
        self.assertEqual(entry.dictionary.entries.filter(entry_type='word').count(),2)

    def test_withdrawal_invalidates_preview_and_shared_word_audio(self):
        first,entry=self.translated();run=self.stage_two(first.port);item=run.items.get();self.analyse(item)
        self.accept_words(item)
        # The source picture belongs to the original contributor, not the port owner.
        with self.captureOnCommitCallbacks(execute=True):withdraw_all(self.user,self.d.pk,0)
        with patch('community_dictionary.tts.synthesize') as api:
            for clip in run.speech.all():jobs.speak(clip.pk)
            self.assertFalse(api.called)
        self.assertFalse(run.speech.exclude(report={}).exists())
        with self.assertRaises(Conflict):vocab.current_item(run.items.get())
        self.assertEqual(self.client.get(reverse('community_dictionary:port-media',args=[self.d.pk,run.pk,item.pk,'image'])).status_code,404)

    def test_foreign_user_cannot_quote_review_or_accept_vocabulary(self):
        first,entry=self.translated();run=self.stage_two(first.port);item=run.items.get();self.analyse(item)
        self.client.force_login(self.outsider)
        for name,args in [('port-vocabulary',[self.d.pk,first.port_id]),('port-review',[self.d.pk,run.pk,item.pk]),('port-run',[self.d.pk,run.pk])]:
            self.assertEqual(self.client.get(reverse('community_dictionary:'+name,args=args)).status_code,404)

    def test_existing_port_can_be_repaired_without_changing_sentence_or_audio(self):
        self.sentence()
        old=legacy_tests.SentencePortingTests.quote(self,language='French');old=self.approve(old)
        while old.items.filter(status='queued').exists():
            for item in list(old.items.filter(status='queued')):
                self.process(item,legacy_tests.SentencePortingTests.answer(self,item));self.save(item)
        entry=old.port.destination.entries.get(entry_type='sentence')
        before=list(entry.contributions.values_list('pk','file_path'))
        legacy_words=list(old.port.destination.entries.filter(entry_type='word'))
        run=self.stage_two(old.port);item=run.items.get()
        words=[{'lemma':'se coucher','meaning':'lie down','surface':'est couché','existing_id':0}]
        self.analyse(item,words);self.accept_words(item,words);self.finish_audio(run)
        self.assertEqual(list(entry.contributions.values_list('pk','file_path')),before)
        self.assertEqual(set(capture.sentence_links(entry.dictionary).values_list('word_entry__word',flat=True)),{'se coucher'})
        self.assertFalse(entry.dictionary.entries.filter(pk__in=[w.pk for w in legacy_words],archived=False).exists())
        next_translation=self.quote(language='French',port=old.port)
        self.assertEqual(next_translation.items.count(),0)

    def test_parser_requires_sentence_surfaces_and_uses_shared_mwe_rules(self):
        data={'sentence':'Der Mann zieht seine Jacke an.','vocabulary':[]}
        words=[{'surface':'zieht … an','lemma':'anziehen','meaning':'put on','existing_id':999}]
        response=SimpleNamespace(status='completed',output_text=json.dumps({'words':words}))
        parsed=port_vocabulary_ai.parse(response,data)
        self.assertEqual(parsed['words'][0]['existing_id'],0)
        response.output_text=json.dumps({'words':[dict(words[0],surface='repose')]})
        with self.assertRaises(ValueError):port_vocabulary_ai.parse(response,data)

    def test_stage_two_blocked_until_unflagged_sentence_previews_reviewed(self):
        self.sentence();run=self.approve(self.quote(language='French'));item=run.items.get();self.process(item,response(word=SENTENCE))
        with self.assertRaises(Conflict):vocab.quote(self.owner,run.port,uuid.uuid4())
        item.needs_attention=True;item.save(update_fields=['needs_attention'])
        self.assertEqual(vocab.quote(self.owner,run.port,uuid.uuid4()).items.count(),0)

    def test_legacy_derived_previews_are_discarded_only_after_repair_approval(self):
        self.sentence();old=self.approve(legacy_tests.SentencePortingTests.quote(self,language='French'))
        while old.items.filter(status='queued').exists():
            for item in list(old.items.filter(status='queued')):
                self.process(item,legacy_tests.SentencePortingTests.answer(self,item))
        self.save(old.items.get(source_entry__entry_type='sentence'))
        run=vocab.quote(self.owner,old.port,uuid.uuid4())
        self.assertEqual(old.items.filter(status='ready').count(),4)
        self.approve(run)
        self.assertEqual(old.items.filter(status='discarded').count(),4)
        self.assertTrue(old.items.filter(status='saved').exists())

    def test_manually_changed_old_word_is_preserved_by_repair(self):
        self.sentence();old=self.approve(legacy_tests.SentencePortingTests.quote(self,language='French'))
        while old.items.filter(status='queued').exists():
            for item in list(old.items.filter(status='queued')):
                self.process(item,legacy_tests.SentencePortingTests.answer(self,item));self.save(item)
        word=old.port.destination.entries.get(word='être couché')
        add_contributions(word,self.owner,{'meaning':'my special sense','edit_text':True},[],publish=True)
        run=self.stage_two(old.port);item=run.items.get()
        words=[{'lemma':'se coucher','meaning':'lie down','surface':'est couché','existing_id':0}]
        self.analyse(item,words);self.accept_words(item,words);self.finish_audio(run)
        word.refresh_from_db();self.assertFalse(word.archived);self.assertEqual(word.meaning,'my special sense')

    def test_failed_analysis_settles_without_creating_or_archiving_words(self):
        first,entry=self.translated();run=self.stage_two(first.port);item=run.items.get()
        with patch.object(port_vocabulary_ai,'analyse',side_effect=TimeoutError),self.captureOnCommitCallbacks(execute=True):
            jobs.process_item(item.pk)
        item.refresh_from_db();run.refresh_from_db()
        self.assertEqual(item.status,'failed');self.assertTrue(item.uncertain_cost)
        self.assertTrue(run.settled);self.assertFalse(run.speech.exists())
        self.assertFalse(VocabularyState.objects.filter(sentence=entry).exists())

    def test_cancellation_during_speech_discards_result_and_accounts_returned_cost(self):
        first,entry=self.translated();run=self.stage_two(first.port);item=run.items.get();self.analyse(item);self.accept_words(item)
        clip=run.speech.first()
        def delayed(*args,report,**kwargs):
            porting.cancel(self.owner,run.pk)
            report.update(speech_cost_usd='0.01',guidance_cost_usd='0')
            return speech()
        with patch('community_dictionary.tts.synthesize',side_effect=delayed):jobs.speak(clip.pk)
        clip.refresh_from_db();run.refresh_from_db()
        self.assertEqual(clip.status,'discarded');self.assertEqual(clip.report,{})
        self.assertFalse(clip.entry.contributions.filter(kind='audio').exists())
        self.assertTrue(run.settled);self.assertGreaterEqual(run.charged_usd,Decimal('.01'))

    def test_word_audio_is_private_and_removed_with_source_then_restorable(self):
        first,entry=self.translated();run=self.stage_two(first.port);item=run.items.get();self.analyse(item)
        self.accept_words(item);self.finish_audio(run)
        word=entry.dictionary.entries.get(word='reposer');audio=word.contributions.get(kind='audio')
        with self.captureOnCommitCallbacks(execute=True):withdraw_all(self.user,self.d.pk,0)
        audio.refresh_from_db();self.assertTrue(audio.entry.dictionary.personal)
        self.assertEqual(audio.withdrawn_from_id,word.pk)
        self.assertFalse(word.contributions.filter(kind='audio').exists())
        self.assertFalse(run.speech.exclude(report={}).exists())
        restore_all(self.user,self.d.pk,1)
        audio.refresh_from_db();self.assertEqual(audio.status,'accepted');self.assertEqual(audio.entry_id,word.pk)
        self.assertTrue(capture.sentence_links(entry.dictionary).filter(word_entry=word).exists())
