"""Automatic batches: real orchestration/ledger/storage with mocked providers."""
from decimal import Decimal
from io import StringIO
import json
from types import SimpleNamespace
from unittest.mock import patch
import uuid

from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse

from community_dictionary import automatic, batch_descriptions, porting, port_tasks, port_vocabulary
from community_dictionary import port_vocabulary_tasks as jobs
from community_dictionary.models import (Contribution, Entry, LanguageCheck, PortItem, PortRun,
    PortSpeech, SentenceWord, VocabularyState)
from community_dictionary.services import Conflict, add_contributions
from community_dictionary.participation import withdraw_all
from projects.models import CreditAccount, CreditLedgerEntry
from . import test_batch_descriptions as fixtures
from .test_batch_descriptions import description, WORDS
from .test_porting import response, speech
from .test_port_reliability import language_response


def vocabulary(data, *args, **kwargs):
    words = ([{'lemma':'chat','meaning':'cat','surface':'chat','existing_id':0},
              {'lemma':'canapé','meaning':'sofa','surface':'canapé','existing_id':0}]
             if data['target_language']=='French' else WORDS)
    return SimpleNamespace(status='completed',output_text=json.dumps({'words':words}),
                           usage=SimpleNamespace(input_tokens=900,output_tokens=100))


@override_settings(OPENAI_API_KEY='fixture-only', CREDITS_ENABLED=False,
    COMMUNITY_DICTIONARY_PORT_WINDOW=2)
class AutomaticTests(TestCase):
    url=fixtures.BatchDescriptionTests.url
    post=fixtures.BatchDescriptionTests.post
    create_entry=fixtures.BatchDescriptionTests.create_entry
    picture=fixtures.BatchDescriptionTests.picture

    def setUp(self):
        fixtures.BatchDescriptionTests.setUp(self)
        self.patches = [patch('community_dictionary.port_tasks.send'),
            patch('community_dictionary.port_vocabulary_tasks.send_speech'),
            patch('community_dictionary.batch_descriptions.interpret',return_value=description()),
            patch('community_dictionary.port_ai.translate',return_value=response(
                word='Le chat est sur le canapé.',meaning='The cat is on the sofa.',category='')),
            patch('community_dictionary.port_vocabulary_ai.analyse',side_effect=vocabulary),
            patch('community_dictionary.tts.synthesize',side_effect=speech)]
        self.send,self.send_speech,self.describe,self.translate,self.analyse,self.speech = [p.start() for p in self.patches]
        for p in self.patches:self.addCleanup(p.stop)

    def quote(self, **kwargs):
        return batch_descriptions.quote(self.owner,self.dictionary,uuid.uuid4(),automatic=True,**kwargs)

    def conversion(self, **kwargs):
        source=self.picture(word='Katten ligger på soffan.',meaning='The cat is on the sofa.')
        source.entry_type='sentence';source.save(update_fields=['entry_type'])
        return porting.quote(self.owner,self.dictionary,
            dict(name='French copy',language='French',explanation_language='English',voice='marin'),
            uuid.uuid4(),automatic=True,**kwargs)

    def approve(self, run):
        with self.captureOnCommitCallbacks(execute=True):
            result=porting.approve(self.owner,run.pk)
        result.refresh_from_db()
        return result

    def process(self, pk):
        with self.captureOnCommitCallbacks(execute=True):
            port_tasks.process_item(pk)

    def drain(self):
        for _ in range(100):
            items=list(PortItem.objects.filter(run__status='running',status='queued'))
            clips=list(PortSpeech.objects.filter(run__status='running',status='queued'))
            if not items and not clips:return
            for item in items:self.process(item.pk)
            for clip in clips:
                with self.captureOnCommitCallbacks(execute=True):jobs.speak(clip.pk)
        self.fail('Background work failed to terminate')

    def child(self, run):
        run.refresh_from_db()
        return PortRun.objects.get(pk=run.options['automatic_child'])

    def audit(self):
        out=StringIO();call_command('community_credit_audit',username=self.owner.username,stdout=out)
        self.assertIn('Reconciliation warnings: 0',out.getvalue())

    def test_images_publish_sentences_shared_words_and_audio_without_reviews(self):
        self.picture(pending=True,meaning='our cat');self.picture()
        run=self.approve(self.quote());self.drain();child=self.child(run)
        self.assertEqual(run.items.filter(status='saved').count(),2)
        self.assertEqual(child.items.filter(status='saved').count(),2)
        self.assertTrue(child.settled)
        self.assertEqual(SentenceWord.objects.count(),4)
        self.assertEqual(child.speech.count(),2)
        sentences=self.dictionary.entries.filter(entry_type='sentence')
        self.assertEqual(sentences.count(),2)
        self.assertEqual(Contribution.objects.filter(kind='audio',status='accepted').count(),4)
        first=sentences.first()
        self.assertTrue(first.current_text.provenance['automatic_publication'])
        self.assertNotIn('accepted_by',first.current_text.provenance)
        self.assertFalse(LanguageCheck.objects.exists())
        self.assertTrue(Contribution.objects.filter(entry__in=sentences,kind='image',author=self.member).exists())
        self.assertEqual(self.quote().allowance_usd,0)

    def test_conversion_uses_translated_sentence_and_shares_provenance(self):
        run=self.approve(self.conversion());self.drain();child=self.child(run)
        self.assertTrue(child.settled)
        data=self.analyse.call_args.args[0]
        self.assertEqual(data['sentence'],'Le chat est sur le canapé.')
        text=child.items.get().source_entry.current_text
        self.assertTrue(text.provenance['automatic_publication']);self.assertNotIn('reviewed_by',text.provenance)
        self.assertEqual(set(child.port.target.entries.filter(entry_type='word').values_list('word',flat=True)),{'chat','canapé'})

    @override_settings(CREDITS_ENABLED=True)
    def test_whole_job_approval_and_atomic_credit_transfer_reconcile_once(self):
        CreditAccount.objects.create(user=self.owner,balance_usd=Decimal('10'))
        self.picture();run=self.quote();ceiling=run.allowance_usd
        self.assertEqual(CreditLedgerEntry.objects.count(),0)
        sentence_allowance=sum(run.items.values_list('allowance_usd',flat=True))
        self.assertGreater(ceiling,sentence_allowance)
        run=self.approve(run)
        self.assertEqual(CreditAccount.objects.get(user=self.owner).balance_usd,Decimal('10')-ceiling)
        self.assertEqual(self.approve(run).pk,run.pk)
        self.drain();child=self.child(run)
        self.assertTrue(child.settled);self.assertTrue(run.settled)
        self.assertLessEqual(child.reserved_usd,Decimal(run.options['automatic_vocabulary_reserve']))
        cost=run.charged_usd+child.charged_usd
        self.assertLessEqual(cost,ceiling)
        self.assertEqual(CreditAccount.objects.get(user=self.owner).balance_usd,Decimal('10')-cost)
        for _ in range(3):
            with self.captureOnCommitCallbacks(execute=True):port_tasks.dispatch(run.pk)
        self.assertEqual(PortRun.objects.count(),2)
        self.assertEqual(self.analyse.call_count,1)
        self.audit()

    @override_settings(CREDITS_ENABLED=True)
    def test_insufficient_balance_for_second_stage_blocks_before_any_calls(self):
        self.picture();run=self.quote()
        CreditAccount.objects.create(user=self.owner,balance_usd=run.items.get().allowance_usd)
        with self.assertRaises(Conflict):self.approve(run)
        self.assertFalse(self.describe.called);self.assertEqual(CreditLedgerEntry.objects.count(),0)

    def test_old_manual_route_still_stops_for_review(self):
        self.picture();run=batch_descriptions.quote(self.owner,self.dictionary,uuid.uuid4())
        self.approve(run);self.drain();run.refresh_from_db()
        self.assertEqual(run.items.get().status,'ready');self.assertFalse(self.analyse.called)
        self.assertEqual(self.dictionary.entries.filter(entry_type='sentence').count(),0)

    def test_quote_replay_cannot_change_mode(self):
        self.picture();run=self.quote()
        with self.assertRaises(Conflict):batch_descriptions.quote(self.owner,self.dictionary,run.pk)

    def test_wrong_language_published_with_flag_but_no_words_or_audio(self):
        self.picture();run=self.approve(self.quote())
        with patch('community_dictionary.port_language.check',return_value=language_response('mismatch')):
            self.drain()
        item=run.items.get();run.refresh_from_db()
        self.assertEqual(item.status,'saved');self.assertTrue(item.needs_attention)
        self.assertFalse(self.speech.called);self.assertFalse(self.analyse.called)
        self.assertEqual(automatic.summary(run)['attention'],1)
        retry=automatic.retry_quote(self.owner,run,uuid.uuid4())
        self.assertEqual(retry.allowance_usd,0)
        sentence=item.saved_entry
        LanguageCheck.objects.create(entry=sentence,text=sentence.current_text,
            meaning=sentence.current_meaning,checked_by=self.owner)
        checked_retry=automatic.retry_quote(self.owner,run,uuid.uuid4())
        self.assertTrue(checked_retry.options['automatic_existing'])

    def test_no_usable_sentence_finishes_with_attention(self):
        self.picture();run=self.approve(self.quote())
        self.describe.return_value=description(sentence='',translation='',outcome='clarify')
        self.drain();run.refresh_from_db()
        self.assertTrue(run.settled);self.assertEqual(run.items.get().status,'failed')
        self.assertFalse(self.analyse.called)

    def test_failed_vocabulary_retries_without_retranslating(self):
        self.picture();run=self.approve(self.quote())
        self.analyse.side_effect=TimeoutError
        self.drain();child=self.child(run);self.assertTrue(child.settled)
        self.assertEqual(child.items.get().status,'failed')
        retry=automatic.retry_quote(self.owner,run,uuid.uuid4())
        self.assertEqual(retry.items.count(),0);self.assertTrue(retry.options['automatic_existing'])
        self.analyse.side_effect=vocabulary
        self.approve(retry);self.drain()
        self.assertEqual(self.describe.call_count,1)
        self.assertTrue(self.child(retry).settled)

    def test_failed_audio_retries_only_missing_clips(self):
        self.picture();run=self.approve(self.quote())
        self.speech.side_effect=TimeoutError
        self.drain();child=self.child(run)
        self.assertEqual(child.speech.filter(status='failed').count(),2)
        self.assertEqual(self.describe.call_count,1);self.assertEqual(self.analyse.call_count,1)
        retry=automatic.retry_quote(self.owner,run,uuid.uuid4())
        self.assertEqual(retry.items.count(),0)
        self.speech.side_effect=speech;self.speech.reset_mock()
        self.approve(retry);self.drain()
        self.assertEqual(self.describe.call_count,1);self.assertEqual(self.analyse.call_count,1)
        self.assertEqual(self.speech.call_count,3)
        self.assertTrue(self.child(retry).settled)

    def test_cancel_after_sentence_stage_stops_automatic_child(self):
        self.picture();run=self.approve(self.quote());self.process(run.items.get().pk)
        child=self.child(run)
        with self.captureOnCommitCallbacks(execute=True):porting.cancel(self.owner,run.pk)
        self.drain();child.refresh_from_db()
        self.assertEqual(child.status,'cancelled');self.assertFalse(self.analyse.called)
        self.assertEqual(self.dictionary.entries.filter(entry_type='sentence').count(),1)

    def test_cancel_before_processing_creates_no_content(self):
        self.picture();run=self.approve(self.quote())
        with self.captureOnCommitCallbacks(execute=True):porting.cancel(self.owner,run.pk)
        self.drain();self.assertFalse(self.describe.called);self.assertFalse(self.analyse.called)
        self.assertEqual(PortRun.objects.count(),1)

    def test_withdrawal_during_paid_call_prevents_publication(self):
        self.picture(pending=True);run=self.approve(self.quote())
        def withdraw(*args,**kwargs):
            withdraw_all(self.member,self.dictionary.pk,0)
            return description()
        self.describe.side_effect=withdraw
        self.drain()
        self.assertEqual(self.dictionary.entries.filter(entry_type='sentence').count(),0)
        self.assertFalse(self.analyse.called)
        self.assertEqual(run.items.get().status,'discarded')

    def test_human_edit_before_vocabulary_request_is_kept(self):
        self.picture();run=self.approve(self.quote());self.process(run.items.get().pk)
        child=self.child(run);entry=child.items.get().source_entry
        add_contributions(entry,self.owner,{'word':'Min egen mening.','edit_text':True},[],publish=True)
        self.drain();entry.refresh_from_db();child.refresh_from_db()
        self.assertEqual(entry.word,'Min egen mening.');self.assertFalse(self.analyse.called)
        self.assertTrue(child.settled)

    def test_existing_reviewed_sentence_needs_no_translation(self):
        self.picture();manual=batch_descriptions.quote(self.owner,self.dictionary,uuid.uuid4())
        self.approve(manual);self.drain();item=manual.items.get()
        porting.save_item(self.owner,item.pk,item.result)
        run=self.quote();self.assertEqual(run.items.count(),0)
        self.approve(run);self.drain()
        self.assertEqual(self.describe.call_count,1);self.assertEqual(self.analyse.call_count,1)
        self.assertTrue(self.child(run).settled)

    def test_automatic_vocabulary_only_option(self):
        self.picture();manual=batch_descriptions.quote(self.owner,self.dictionary,uuid.uuid4())
        self.approve(manual);self.drain();item=manual.items.get()
        porting.save_item(self.owner,item.pk,item.result)
        run=port_vocabulary.quote(self.owner,manual.port,uuid.uuid4(),automatic=True)
        self.approve(run);self.drain();run.refresh_from_db()
        self.assertTrue(run.settled);self.assertEqual(run.items.get().status,'saved')

    def test_public_and_owner_labels_do_not_claim_human_review(self):
        self.picture();run=self.approve(self.quote());self.drain()
        sentence=run.items.get().saved_entry
        self.dictionary.public_browsing_enabled=True;self.dictionary.save()
        url=reverse('community_dictionary:public-entry',args=[self.dictionary.pk,sentence.pk])
        self.client.logout()
        self.assertContains(self.client.get(url),'published automatically without human review')
        LanguageCheck.objects.create(entry=sentence,text=sentence.current_text,
            meaning=sentence.current_meaning,checked_by=self.owner)
        self.assertNotContains(self.client.get(url),'without human review')

    def test_ui_has_combined_estimate_progress_and_owner_only_approval(self):
        self.picture();run=self.quote();url=self.url('port-run',run.pk)
        page=self.client.get(url);self.assertContains(page,'Approve and create everything')
        self.assertContains(page,'estimate for the whole job')
        self.client.force_login(self.member)
        self.assertEqual(self.client.post(self.url('port-action',run.pk),{'action':'approve','approve':'on'}).status_code,404)
        self.client.force_login(self.owner);self.approve(run);self.drain()
        page=self.client.get(url)
        self.assertContains(page,'Processing finished');self.assertContains(page,'Browse dictionary')
        self.assertNotContains(page,'Continue reviewing and saving')
        self.assertEqual(self.client.get(self.url('port-run',self.child(run).pk)).status_code,302)

    def test_changed_model_at_transition_keeps_results_and_stops(self):
        self.picture();run=self.approve(self.quote())
        original=automatic.vocabulary.VERSION
        with patch.object(automatic.vocabulary,'VERSION',original+'-new'):
            self.drain()
        run.refresh_from_db();self.assertTrue(run.settled)
        self.assertIn('automatic_error',run.options);self.assertFalse(self.analyse.called)
        with self.captureOnCommitCallbacks(execute=True):port_tasks.resume(self.owner,run.pk)
        self.drain();self.assertTrue(self.child(run).settled)

    @override_settings(CREDITS_ENABLED=True)
    def test_expensive_followon_pauses_within_preapproved_credit(self):
        CreditAccount.objects.create(user=self.owner,balance_usd=Decimal('10'))
        self.picture();run=self.approve(self.quote());cap=run.allowance_usd
        # Change only the forecast, not configured tariffs. Actual child work
        # must remain capped by the original approval even if the text is longer.
        with patch.object(port_vocabulary,'estimate',return_value=(Decimal('10'),Decimal('25'))):
            self.process(run.items.get().pk)
        child=self.child(run)
        self.assertLessEqual(child.allowance_usd,Decimal(run.options['automatic_vocabulary_reserve']))
        with patch('community_dictionary.port_vocabulary_tasks.port_costs.analysis',return_value=Decimal('100')):
            self.drain()
        child.refresh_from_db();self.assertEqual(child.items.get().status,'budget')
        self.assertFalse(self.analyse.called)
        self.assertLessEqual(Decimal('10')-CreditAccount.objects.get(user=self.owner).balance_usd,cap)
        with self.captureOnCommitCallbacks(execute=True):porting.cancel(self.owner,run.pk)
        self.audit()
