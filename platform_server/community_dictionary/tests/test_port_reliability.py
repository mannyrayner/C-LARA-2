"""Regression coverage for CJK, language checks, bounded holds and audio recovery."""
from datetime import timedelta
from decimal import Decimal
from io import StringIO
import json
from types import SimpleNamespace
import uuid
from unittest.mock import MagicMock, patch

from django.core.management import call_command
from django.test import TestCase, SimpleTestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from community_dictionary import (capture_vocabulary, port_audio, port_budget,
    port_language, port_tasks, porting, port_vocabulary as vocab, port_vocabulary_tasks as jobs)
from community_dictionary.models import Entry, SentenceWord
from community_dictionary.services import Conflict, add_contributions
from projects.models import CreditAccount, CreditLedgerEntry
from . import test_port_vocabulary as fixtures
from .test_port_vocabulary import WORDS, SENTENCE
from .test_porting import response, speech


def language_response(verdict):
    return SimpleNamespace(status='completed', output_text=json.dumps({'verdict':verdict}),
        usage=SimpleNamespace(input_tokens=150, output_tokens=10))


class SpanTests(SimpleTestCase):
    def test_unspaced_han_kana_and_inflected_korean(self):
        for sentence, forms in [
            ('猫がソファで寝ています。', ['猫','ソファ','寝ています']),
            ('猫躺在沙发上。', ['猫','躺','沙发']),
            ('고양이가 소파에서 자고 있어요.', ['고양이가','소파에서','자고 있어요.']),
        ]:
            for form in forms:
                with self.subTest(form=form):
                    self.assertTrue(capture_vocabulary.aligned_surface(form,sentence))

    def test_script_local_boundaries_do_not_admit_unrelated_latin_substrings(self):
        for form, sentence in [('att','Katten sover.'), ('at','猫 watches a cat.'),
                              ('고양이','고양이가 자요.'), ('沙 发','猫在沙发上。')]:
            with self.subTest(form=form):
                self.assertFalse(capture_vocabulary.aligned_surface(form,sentence))
        self.assertTrue(capture_vocabulary.aligned_surface('cat','猫catです。'))
        self.assertTrue(capture_vocabulary.aligned_surface('zieht … an','Er zieht seine Jacke an.'))
        self.assertFalse(capture_vocabulary.aligned_surface('an … zieht','Er zieht seine Jacke an.'))

    def test_language_checker_has_bounded_text_only_contract(self):
        client=MagicMock()
        with patch.object(port_language,'_openai_client',return_value=client) as factory:
            port_language.check('Un chat dort.','Italian',model='fixture',api_key='fixture')
        self.assertEqual(factory.call_args.kwargs['max_retries'],0)
        request=client.__enter__.return_value.responses.create.call_args.kwargs
        self.assertFalse(request['store'])
        self.assertEqual(json.loads(request['input'][0]['content']),
                         {'sentence':'Un chat dort.','target_language':'Italian'})
        self.assertEqual(port_language.parse(language_response('mismatch')),'mismatch')
        with self.assertRaises(ValueError):port_language.parse(language_response('invented'))


@override_settings(OPENAI_API_KEY='fixture-only', CREDITS_ENABLED=False,
    COMMUNITY_DICTIONARY_PORT_WINDOW=2, PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class ReliabilityTests(TestCase):
    # Reuse setup/actions only, not an inherited duplicate test suite.
    setUp=fixtures.PortVocabularyTests.setUp
    start=fixtures.PortVocabularyTests.start
    action=fixtures.PortVocabularyTests.action
    ready=fixtures.PortVocabularyTests.ready
    publish=fixtures.PortVocabularyTests.publish
    url=fixtures.PortVocabularyTests.url
    sentence=fixtures.PortVocabularyTests.sentence
    approve=fixtures.PortVocabularyTests.approve
    process=fixtures.PortVocabularyTests.process
    save=fixtures.PortVocabularyTests.save
    quote=fixtures.PortVocabularyTests.quote
    translated=fixtures.PortVocabularyTests.translated
    stage_two=fixtures.PortVocabularyTests.stage_two
    analyse=fixtures.PortVocabularyTests.analyse
    accept_words=fixtures.PortVocabularyTests.accept_words
    finish_audio=fixtures.PortVocabularyTests.finish_audio

    def audit(self):
        output=StringIO()
        call_command('community_credit_audit',username=self.owner.username,stdout=output)
        self.assertIn('Reconciliation warnings: 0',output.getvalue())
        return output.getvalue()

    def test_japanese_full_vocabulary_path_and_manual_edit(self):
        source=self.sentence()
        run=self.approve(self.quote(language='Japanese'),balance='100')
        item=run.items.get()
        self.process(item,response(word='猫がソファで寝ています。',meaning=source.meaning,category=''))
        entry=self.save(item)
        second=self.stage_two(run.port);candidate=second.items.get()
        words=[{'lemma':'猫','meaning':'cat','surface':'猫','existing_id':0},
               {'lemma':'ソファ','meaning':'sofa','surface':'ソファ','existing_id':0},
               {'lemma':'寝る','meaning':'sleep','surface':'寝ています','existing_id':0}]
        self.analyse(candidate,words)
        page=self.client.get(self.url('port-review',second.pk,candidate.pk))
        self.assertContains(page,'寝ています')
        data={'words-TOTAL_FORMS':'3','words-INITIAL_FORMS':'3','action':'save'}
        for index,word in enumerate(words):
            for key,value in word.items():data[f'words-{index}-{key}']=value
        with patch.object(jobs,'send_speech'),self.captureOnCommitCallbacks(execute=True):
            result=self.client.post(self.url('port-review',second.pk,candidate.pk),data)
        self.assertEqual(result.status_code,302)
        self.assertEqual(set(SentenceWord.objects.filter(sentence_text=entry.current_text)
            .values_list('word_entry__word',flat=True)),{'猫','ソファ','寝る'})
        self.finish_audio(second)
        self.assertTrue(second.settled)

    def test_wrong_language_is_kept_editable_skipped_by_bulk_and_has_no_audio(self):
        source=self.sentence();run=self.approve(self.quote(language='Italian'))
        item=run.items.get()
        with patch.object(port_language,'check',return_value=language_response('mismatch')) as check:
            _,synth=self.process(item,response(word='Le chat dort.',meaning=source.meaning,category=''))
        self.assertFalse(synth.called)
        self.assertEqual(check.call_args.args[:2],('Le chat dort.','Italian'))
        self.assertEqual(item.usage,{'input_tokens':1350,'output_tokens':110})
        self.assertTrue(item.needs_attention)
        self.assertEqual(porting.accept_remaining(self.owner,run.pk),(0,0))
        self.assertContains(self.client.get(self.url('port-review',run.pk,item.pk)),'target-language check')
        entry=self.save(item,word='Il gatto dorme.')
        self.assertEqual(entry.word,'Il gatto dorme.')
        self.assertFalse(entry.contributions.filter(kind='audio').exists())
        recovery=port_audio.quote(self.owner,run,uuid.uuid4())
        self.assertEqual(recovery.items.get().snapshot['word'],'Il gatto dorme.')

    def test_unavailable_language_check_does_not_lose_text_or_silently_pass(self):
        source=self.sentence();run=self.approve(self.quote(language='Italian'));item=run.items.get()
        with patch.object(port_language,'check',side_effect=TimeoutError):
            _,synth=self.process(item,response(word='Il gatto dorme.',meaning=source.meaning,category=''))
        self.assertFalse(synth.called)
        self.assertTrue(item.needs_attention);self.assertTrue(item.uncertain_cost)
        self.assertEqual(item.result['language_check'],'unavailable')
        self.assertEqual(self.save(item).word,'Il gatto dorme.')

    def missing_sentence(self):
        source=self.sentence();run=self.approve(self.quote(language='French'));item=run.items.get()
        with patch('community_dictionary.port_ai.translate',return_value=response(word=SENTENCE,meaning=source.meaning)), \
                patch('community_dictionary.tts.synthesize',side_effect=TimeoutError),patch.object(port_tasks,'send'):
            port_tasks.process_item(item.pk)
        entry=self.save(item);run.refresh_from_db()
        return run,entry

    def approve_audio(self,run):
        with patch.object(jobs,'send_speech'),self.captureOnCommitCallbacks(execute=True):
            return porting.approve(self.owner,run.pk)

    def test_recovery_only_generates_current_missing_audio_and_is_idempotent(self):
        first,entry=self.missing_sentence()
        original_charge=first.charged_usd
        add_contributions(entry,self.owner,{'word':'Un bijou repose ici.','edit_text':True},[],publish=True)
        token=uuid.uuid4()
        with patch('community_dictionary.port_ai.translate') as translate,patch('community_dictionary.tts.synthesize') as synth:
            run=port_audio.quote(self.owner,first,token)
            self.assertEqual(run.pk,port_audio.quote(self.owner,first,token).pk)
            self.assertFalse(translate.called);self.assertFalse(synth.called)
        self.assertEqual(run.items.count(),1)
        self.approve_audio(run);self.approve_audio(run)
        self.assertEqual(run.speech.count(),1)
        with patch('community_dictionary.port_ai.translate') as translate:
            synth=self.finish_audio(run)
            self.assertFalse(translate.called)
        self.assertEqual(synth.call_count,1)
        self.assertEqual(synth.call_args.args[0],'Un bijou repose ici.')
        self.assertEqual(synth.call_args.kwargs['speech_kind'],'sentence')
        self.assertEqual(synth.call_args.kwargs['language'],'fr')
        self.assertEqual(entry.contributions.filter(kind='audio',status='accepted').count(),1)
        first.refresh_from_db();self.assertEqual(first.charged_usd,original_charge)
        self.finish_audio(run)
        with self.assertRaises(Conflict):port_audio.quote(self.owner,first,uuid.uuid4())

    def test_recovery_rejects_other_user_and_changed_approved_wording(self):
        first,entry=self.missing_sentence()
        with self.assertRaises(Conflict):port_audio.quote(self.user,first,uuid.uuid4())
        run=port_audio.quote(self.owner,first,uuid.uuid4())
        add_contributions(entry,self.owner,{'word':'Autre phrase.','edit_text':True},[],publish=True)
        with self.assertRaises(Conflict):self.approve_audio(run)
        self.assertFalse(run.speech.exists())
        self.client.force_login(self.user)
        self.assertEqual(self.client.post(self.url('port-action',first.pk),{
            'action':'audio-estimate','submission_id':str(uuid.uuid4())}).status_code,404)

    def test_vocabulary_recovery_skips_successful_shared_words(self):
        first,entry=self.translated();run=self.stage_two(first.port)
        item=run.items.get();self.analyse(item);self.accept_words(item)
        with patch('community_dictionary.tts.synthesize',side_effect=[speech(),TimeoutError]), \
                patch.object(jobs,'send_speech'),self.captureOnCommitCallbacks(execute=True):
            for clip in run.speech.all():jobs.speak(clip.pk)
        run.refresh_from_db();self.assertTrue(run.settled)
        retry=port_audio.quote(self.owner,run,uuid.uuid4())
        self.assertEqual(retry.items.count(),1)
        failed=run.speech.get(status='failed')
        self.assertEqual(retry.items.get().source_entry_id,failed.entry_id)
        self.approve_audio(retry);synth=self.finish_audio(retry)
        self.assertEqual(synth.call_count,1)
        self.assertEqual(synth.call_args.kwargs['speech_kind'],'entry')

    def test_recovery_of_interrupted_audio_never_replays_uncertain_request(self):
        first,entry=self.missing_sentence();run=port_audio.quote(self.owner,first,uuid.uuid4())
        self.approve_audio(run)
        clip=run.speech.get();clip.status='running';clip.started_at=timezone.now()-timedelta(minutes=20);clip.save()
        with patch.object(jobs,'send_speech'),patch.object(port_tasks,'send'), \
                patch('community_dictionary.tts.synthesize') as synth,self.captureOnCommitCallbacks(execute=True):
            port_tasks.resume(self.owner,run.pk)
        clip.refresh_from_db();run.refresh_from_db()
        self.assertFalse(synth.called);self.assertEqual(clip.status,'failed');self.assertTrue(run.settled)

    @override_settings(CREDITS_ENABLED=True)
    def test_pause_topup_once_partial_refund_and_final_audit(self):
        with override_settings(CREDITS_ENABLED=False):first,entry=self.translated()
        second=Entry.objects.create(dictionary=entry.dictionary,created_by=self.owner,entry_type='sentence')
        add_contributions(second,self.owner,{'word':SENTENCE,'meaning':entry.meaning},[],publish=True)
        run=vocab.quote(self.owner,first.port,uuid.uuid4())
        run=self.approve(run,balance='100')
        items=list(run.items.all())
        for item in items:self.analyse(item)
        self.accept_words(items[0])
        # An unusually long/costly provider result consumes the item's forecast.
        items[0].translation_cost=items[0].allowance_usd;items[0].save(update_fields=['translation_cost'])
        with patch('community_dictionary.tts.synthesize') as synth,patch.object(jobs,'send_speech'), \
                self.captureOnCommitCallbacks(execute=True):
            for clip in run.speech.all():jobs.speak(clip.pk)
        self.assertFalse(synth.called)
        run.refresh_from_db();offer=port_budget.offer(run)
        self.assertIsNotNone(offer);self.assertFalse(run.settled)
        old_reserved=run.reserved_usd
        url=self.url('port-action',run.pk)
        self.assertEqual(self.client.post(url,{'action':'approve-more','budget_token':offer['token']}).status_code,400)
        CreditAccount.objects.filter(user=self.owner).update(balance_usd=0)
        with self.assertRaises(Conflict):port_budget.approve_more(self.owner,run.pk,offer['token'])
        CreditAccount.objects.filter(user=self.owner).update(balance_usd=Decimal('100')-old_reserved)
        with self.assertRaises(Conflict):port_budget.approve_more(self.owner,run.pk,offer['token']+'tampered')
        with patch.object(jobs,'send_speech'),self.captureOnCommitCallbacks(execute=True):
            port_budget.approve_more(self.owner,run.pk,offer['token'])
            port_budget.approve_more(self.owner,run.pk,offer['token'])
        run.refresh_from_db()
        self.assertEqual(run.reserved_usd,old_reserved+offer['amount'])
        self.assertEqual(CreditLedgerEntry.objects.filter(metadata__kind='topup').count(),1)
        self.finish_audio(run)
        self.assertFalse(run.settled) # second sentence still awaiting review
        self.assertGreater(run.released_usd,0)
        self.assertEqual(CreditAccount.objects.get(user=self.owner).balance_usd,
                         Decimal('100')-run.reserved_usd+run.released_usd)
        self.audit()
        self.accept_words(items[1]);self.finish_audio(run)
        self.assertTrue(run.settled)
        self.assertEqual(CreditAccount.objects.get(user=self.owner).balance_usd,Decimal('100')-run.charged_usd)
        ledger_count=CreditLedgerEntry.objects.count()
        port_tasks.dispatch(str(run.pk));port_budget.approve_more(self.owner,run.pk,offer['token'])
        self.assertEqual(CreditLedgerEntry.objects.count(),ledger_count)
        self.audit()

    @override_settings(CREDITS_ENABLED=True)
    def test_cancel_paused_jobs_returns_unused_credit_without_provider_calls(self):
        with override_settings(CREDITS_ENABLED=False):first,entry=self.translated()
        run=self.stage_two(first.port);item=run.items.get();self.analyse(item);self.accept_words(item)
        item.translation_cost=item.allowance_usd;item.save(update_fields=['translation_cost'])
        with patch('community_dictionary.tts.synthesize') as synth,patch.object(jobs,'send_speech'),self.captureOnCommitCallbacks(execute=True):
            for clip in run.speech.all():jobs.speak(clip.pk)
            porting.cancel(self.owner,run.pk)
        self.assertFalse(synth.called)
        run.refresh_from_db();self.assertTrue(run.settled)
        self.assertFalse(run.speech.exclude(status='discarded').exists())
        self.audit()

    def test_new_vocabulary_quote_has_bounded_estimate(self):
        first,entry=self.translated();run=vocab.quote(self.owner,first.port,uuid.uuid4())
        # Regression bound for one short sentence: 150 of these formerly held ~$130.
        self.assertLess(run.allowance_usd*150,Decimal('25'))
        self.assertLess(run.estimated_usd*150,Decimal('10'))
        self.assertLessEqual(run.allowance_usd,run.estimated_usd*Decimal('2.5')+Decimal('.0001'))

    def test_translation_cost_can_pause_audio_without_translating_again(self):
        source=self.sentence();run=self.approve(self.quote(language='French'));item=run.items.get()
        costly=response(word=SENTENCE,meaning=source.meaning,category='')
        costly.usage=SimpleNamespace(input_tokens=200000,output_tokens=100)
        _,synth=self.process(item,costly)
        self.assertFalse(synth.called)
        self.assertEqual(item.status,'budget');self.assertEqual(item.phase,'audio')
        self.assertEqual(item.result['word'],SENTENCE)
        run.refresh_from_db();offer=port_budget.offer(run)
        with patch.object(port_tasks,'send'),self.captureOnCommitCallbacks(execute=True):
            port_budget.approve_more(self.owner,run.pk,offer['token'])
        translate,synth=self.process(item)
        self.assertFalse(translate.called);self.assertEqual(synth.call_count,1)
        self.assertEqual(item.status,'ready')
        self.assertEqual(self.save(item).word,SENTENCE)

    def test_audio_recovery_progress_shows_saved_word_and_link(self):
        first,entry=self.missing_sentence()
        action=self.client.post(self.url('port-action',first.pk),{
            'action':'audio-estimate','submission_id':str(uuid.uuid4())})
        self.assertEqual(action.status_code,302)
        page=self.client.get(action['Location'])
        self.assertContains(page,'Recover missing audio')
        run=page.context['run'];self.approve_audio(run);self.finish_audio(run)
        page=self.client.get(action['Location'])
        self.assertContains(page,SENTENCE)
        self.assertContains(page,reverse('community_dictionary:entry',args=[entry.dictionary_id,entry.pk]))

    @override_settings(CREDITS_ENABLED=True)
    def test_legacy_approved_job_keeps_original_settlement(self):
        with override_settings(CREDITS_ENABLED=False):first,entry=self.translated()
        run=vocab.quote(self.owner,first.port,uuid.uuid4())
        run.options={};run.allowance_usd=Decimal('10');run.save()
        run.items.update(allowance_usd=10)
        run=self.approve(run,balance='100');item=run.items.get()
        self.analyse(item);self.accept_words(item);self.finish_audio(run)
        self.assertEqual(run.released_usd,0)
        self.assertEqual(run.reserved_usd,10)
        self.assertEqual(CreditLedgerEntry.objects.filter(metadata__kind='refund').count(),1)
        self.audit()
