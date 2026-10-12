"""Linked language versions: accepted sentences, explicit costs, protected edits."""
from unittest.mock import patch

from django.test import TestCase, override_settings, Client
from django.urls import reverse

from community_dictionary import workflow, porting, port_vocabulary as vocab
from community_dictionary.models import (Dictionary, Entry, PortRun,
    VocabularyState, Participation, MembershipRequest)
from community_dictionary.services import add_contributions, Conflict
from community_dictionary.storage import prepare_upload
from projects.models import CreditAccount, CreditLedgerEntry
from . import test_port_vocabulary as fixtures
from .test_porting import response
from .test_workflow import picture


@override_settings(OPENAI_API_KEY='fixture-only', CREDITS_ENABLED=False,
    PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class PortGuidanceTests(TestCase):
    start = fixtures.PortVocabularyTests.start
    action = fixtures.PortVocabularyTests.action
    ready = fixtures.PortVocabularyTests.ready
    publish = fixtures.PortVocabularyTests.publish
    url = fixtures.PortVocabularyTests.url
    sentence = fixtures.PortVocabularyTests.sentence
    approve = fixtures.PortVocabularyTests.approve
    process = fixtures.PortVocabularyTests.process
    save = fixtures.PortVocabularyTests.save
    quote = fixtures.PortVocabularyTests.quote
    translated = fixtures.PortVocabularyTests.translated
    stage_two = fixtures.PortVocabularyTests.stage_two
    analyse = fixtures.PortVocabularyTests.analyse
    accept_words = fixtures.PortVocabularyTests.accept_words
    finish_audio = fixtures.PortVocabularyTests.finish_audio

    def setUp(self):
        fixtures.PortVocabularyTests.setUp(self)
        self.initial, self.french_sentence = self.translated()
        self.port = self.initial.port
        self.french = self.port.destination
        self.french.name = 'French version'
        self.french.save(update_fields=['name'])
        self.mark_current(self.french_sentence)
        self.original = self.initial.items.get().source_entry
        self.client.force_login(self.owner)

    def mark_current(self, entry):
        entry.refresh_from_db()
        VocabularyState.objects.update_or_create(sentence=entry, defaults={
            'snapshot':vocab.sentence_snapshot(entry), 'recipe':vocab.VERSION,
            'words':[], 'accepted_by':self.owner})

    def new_sentence(self, word='En katt sover.', *, pending=False, category=''):
        entry = Entry.objects.create(dictionary=self.d, created_by=self.owner, entry_type='sentence')
        add_contributions(entry, self.owner, {'word':word, 'meaning':'A cat is sleeping.', 'category':category,
            'prepared_photo':prepare_upload(picture(), 'image')}, [], publish=not pending)
        entry.refresh_from_db()
        return entry

    def change(self, entry, **fields):
        add_contributions(entry, self.owner, {**fields, 'edit_text':True}, [], publish=True)
        entry.refresh_from_db()

    def offer(self, dictionary=None, *, details=True):
        dictionary = dictionary or self.french
        dictionary.refresh_from_db()
        return workflow.suggestion(self.owner, dictionary, details=details)

    def submit(self, token, dictionary=None, client=None):
        return (client or self.client).post(reverse('community_dictionary:workflow-start',
            args=[(dictionary or self.french).pk]), {'approval':token})

    def launch(self, dictionary=None):
        dictionary = dictionary or self.french
        offer = self.offer(dictionary)
        with patch('community_dictionary.port_tasks.send'), self.captureOnCommitCallbacks(execute=True):
            result = self.submit(offer['approval'], dictionary)
        self.assertEqual(result.status_code, 302, result.content)
        run = self.port.runs.first()
        self.assertEqual(run.stage, 'sentences')
        self.assertEqual(run.status, 'running')
        self.assertTrue(run.options['sentence_updates'])
        return run

    def test_six_new_sentences_both_cards_read_only_no_source_words(self):
        self.assertIsNone(self.offer())
        for n in range(6):
            self.new_sentence(f'En katt sover {n}.')
        pending = self.new_sentence(pending=True)
        archived = self.new_sentence(); archived.archived=True; archived.save()
        independent = Entry.objects.create(dictionary=self.d, created_by=self.owner)
        add_contributions(independent, self.owner, {'word':'hund','meaning':'dog'}, [], publish=True)
        before = PortRun.objects.count()
        with patch('community_dictionary.port_ai.translate', side_effect=AssertionError('No API')):
            source, target = self.offer(self.d), self.offer()
            self.assertEqual(source['kind'], 'sentences')
            self.assertEqual((target['new_count'],target['changed_count']), (6,0))
            self.assertEqual(source['url'], target['url'])
            self.assertEqual(source['port_id'], target['port_id'])
            page = self.client.get(reverse('community_dictionary:home'))
            self.assertContains(page,'6 new sentences')
            self.assertContains(page,'available from Swedish')
        self.assertEqual(PortRun.objects.count(), before)
        run = self.launch()
        self.assertEqual(run.items.count(),6)
        self.assertFalse(run.items.filter(source_entry__in=[pending,archived,independent,self.original]).exists())

    def test_new_and_changed_counts_and_current_quote_match(self):
        self.new_sentence()
        self.change(self.original, word='Katten sover på soffan.')
        offer = self.offer()
        self.assertEqual((offer['new_count'],offer['changed_count']), (1,1))
        self.assertIn('1 new sentence and 1 changed sentence',offer['label'])
        run = self.launch(self.d)
        self.assertEqual(run.items.count(),2)
        self.assertEqual(run.estimated_usd,offer['estimated'])
        self.assertEqual(run.allowance_usd,offer['allowance'])

    def test_new_category_examples_do_not_retranslate_unchanged_sentences(self):
        self.change(self.original, category='Home')
        run = self.launch()
        self.process(run.items.get(), response(word=self.french_sentence.word,
            meaning=self.french_sentence.meaning, category='Home', category_language='commenting'))
        self.save(run.items.get())
        self.mark_current(self.french_sentence)
        self.assertIsNone(self.offer())
        new = self.new_sentence(category='Home')
        offer = self.offer()
        self.assertEqual((offer['new_count'], offer['changed_count']), (1, 0))
        run = self.launch()
        self.assertEqual(run.items.get().source_entry_id, new.pk)
        # Existing evidence is still checked: an edited category example must
        # invalidate the approved scope instead of silently changing its basis.
        self.change(self.original, meaning='Changed category evidence')
        with self.assertRaises(Conflict):
            porting.current_item(run.items.get())

    def test_manual_french_corrections_and_audio_are_preserved(self):
        before_audio = list(self.french_sentence.contributions.filter(kind='audio').values_list('pk','file_path','status'))
        self.change(self.french_sentence, word='Une correction française personnelle.')
        self.mark_current(self.french_sentence)
        self.change(self.original, word='Katten sover på soffan.')
        self.assertIsNone(self.offer())
        fresh = self.new_sentence()
        offer = self.offer()
        self.assertEqual(offer['protected_count'],1)
        run = self.launch()
        self.assertEqual(run.items.get().source_entry_id,fresh.pk)
        self.process(run.items.get(),response(word='Un chat dort.',meaning='A cat is sleeping.',category=''))
        self.save(run.items.get())
        self.french_sentence.refresh_from_db()
        self.assertEqual(self.french_sentence.word,'Une correction française personnelle.')
        self.assertEqual(before_audio,list(self.french_sentence.contributions.filter(kind='audio').values_list('pk','file_path','status')))

    def test_source_word_edits_alone_do_not_prompt_retranslation(self):
        self.change(self.d.entries.get(word='katt'),word='katten')
        self.assertIsNone(self.offer())
        self.assertIsNone(self.offer(self.d))

    def test_two_stages_derive_words_from_accepted_french_then_prompt_disappears(self):
        self.new_sentence()
        run = self.launch()
        self.assertEqual(self.offer(self.d)['kind'],'related-progress')
        item=run.items.get(); self.process(item,response(word='Un chat repose sur du tissu.',meaning='A cat rests on fabric.',category=''))
        self.assertEqual(self.offer()['kind'],'review')
        self.assertEqual(self.offer(self.d)['kind'],'related-review')
        destination = self.save(item)
        self.assertEqual(self.offer()['kind'],'vocabulary')
        self.assertEqual(self.offer(self.d)['kind'],'related-vocabulary')
        stage=self.stage_two(self.port)
        candidate=stage.items.get(); api=self.analyse(candidate)
        self.assertEqual(api.call_args.args[0]['sentence'],destination.word)
        self.accept_words(candidate); self.finish_audio(stage)
        self.assertTrue(vocab.current_state(destination))
        self.assertIsNone(self.offer())
        self.assertIsNone(self.offer(self.d))

    def test_changed_source_scope_requires_fresh_approval_without_partial_quote(self):
        self.new_sentence(); token=self.offer()['approval']; before=PortRun.objects.count()
        self.new_sentence('En hund springer.')
        self.assertEqual(self.submit(token).status_code,409)
        self.assertEqual(PortRun.objects.count(),before)

    def test_french_edit_after_estimate_requires_fresh_approval(self):
        self.change(self.original,word='Katten sover.')
        token=self.offer()['approval']; before=PortRun.objects.count()
        self.change(self.french_sentence,word='Le chat dort paisiblement.')
        self.assertEqual(self.submit(token).status_code,409)
        self.assertEqual(PortRun.objects.count(),before)

    def test_french_edit_after_generation_cannot_be_overwritten(self):
        self.change(self.original,word='Katten sover.')
        run=self.launch();item=run.items.get()
        self.process(item,response(word='Le chat dort.',meaning='The cat sleeps.',category=''))
        self.change(self.french_sentence,word='Ma propre correction.')
        with self.assertRaises(Conflict):self.save(item)
        self.french_sentence.refresh_from_db();self.assertEqual(self.french_sentence.word,'Ma propre correction.')

    @override_settings(CREDITS_ENABLED=True)
    def test_source_and_destination_approval_cannot_dispatch_or_charge_twice(self):
        self.new_sentence(); CreditAccount.objects.filter(user=self.owner).update(balance_usd=100)
        source_token=self.offer(self.d)['approval']; target_token=self.offer()['approval']
        with patch('community_dictionary.port_tasks.dispatch') as dispatch, self.captureOnCommitCallbacks(execute=True):
            self.assertEqual(self.submit(source_token,self.d).status_code,302)
            self.assertEqual(self.submit(source_token,self.d).status_code,302)
            self.assertEqual(self.submit(target_token).status_code,409)
        self.assertEqual(dispatch.call_count,1)
        self.assertEqual(CreditLedgerEntry.objects.filter(metadata__kind='reservation').count(),1)

    @override_settings(CREDITS_ENABLED=True)
    def test_insufficient_funds_explained_and_no_run_created(self):
        self.new_sentence();CreditAccount.objects.filter(user=self.owner).update(balance_usd=0)
        offer=self.offer();self.assertFalse(offer['enough_funds']);before=PortRun.objects.count()
        self.assertContains(self.client.get(reverse('community_dictionary:dictionary',args=[self.french.pk])),'Insufficient credit')
        self.assertEqual(self.submit(offer['approval']).status_code,409)
        self.assertEqual(PortRun.objects.count(),before)

    def test_policy_and_ownership_changes_hide_notices_and_block_old_tokens(self):
        self.new_sentence(); token=self.offer()['approval']
        for dictionary,field,value in [(self.d,'hidden',True),(self.french,'hidden',True),
                (self.french,'show_workflow_suggestions',False),(self.d,'photo_ai_enabled',False),
                (self.french,'photo_ai_enabled',False),(self.french,'tts_enabled',False),
                (self.d,'archived',True),(self.french,'personal',True)]:
            previous=getattr(dictionary,field)
            Dictionary.objects.filter(pk=dictionary.pk).update(**{field:value})
            self.assertIsNone(self.offer(self.d),field)
            self.assertIsNone(self.offer(),field)
            self.assertIn(self.submit(token).status_code,[404,409])
            Dictionary.objects.filter(pk=dictionary.pk).update(**{field:previous})
        Dictionary.objects.filter(pk=self.d.pk).update(owner=self.user)
        self.assertIsNone(self.offer())
        self.assertIn(self.submit(token).status_code,[404,409])

    def test_source_opt_out_does_not_turn_off_destination_guidance(self):
        self.new_sentence();Dictionary.objects.filter(pk=self.d.pk).update(show_workflow_suggestions=False)
        self.assertIsNone(self.offer(self.d))
        self.assertEqual(self.offer()['kind'],'sentences')

    def test_withdrawal_and_anonymous_visitors_have_no_cross_dictionary_metadata(self):
        self.new_sentence();Participation.objects.create(dictionary=self.d,user=self.owner,withdrawn=True)
        self.assertIsNone(self.offer())
        self.client.logout()
        self.assertEqual(self.client.get(reverse('community_dictionary:dictionary',args=[self.french.pk])).status_code,302)
        self.assertNotContains(self.client.get(reverse('community_dictionary:public-home')),'French version')

    def test_post_csrf_expired_token_and_wrong_dictionary(self):
        self.new_sentence();token=self.offer()['approval']
        csrf=Client(enforce_csrf_checks=True);csrf.force_login(self.owner)
        self.assertEqual(self.submit(token,client=csrf).status_code,403)
        self.assertEqual(self.submit(token,self.d).status_code,409)
        with patch('django.core.signing.time.time',return_value=9999999999):
            self.assertEqual(self.submit(token).status_code,409)
        self.client.force_login(self.user)
        self.assertEqual(self.submit(token).status_code,409)

    def test_membership_requests_keep_priority(self):
        self.new_sentence()
        MembershipRequest.objects.create(dictionary=self.french,user=self.outsider)
        self.assertEqual(self.offer()['kind'],'requests')

    def test_update_can_change_only_commenting_language_preserving_target_audio(self):
        other=self.approve(self.quote(language='Swedish',explanation='French'))
        item=other.items.get();self.process(item,response(word=self.original.word,meaning='Un chat est sur le canapé.',category=''))
        translated=self.save(item);self.mark_current(translated)
        self.new_sentence()
        offer=self.offer(other.port.destination);self.assertEqual(offer['kind'],'sentences')
        self.assertEqual(offer['new_count'],1)
        with patch('community_dictionary.port_tasks.send'),self.captureOnCommitCallbacks(execute=True):
            result=self.submit(offer['approval'],other.port.destination)
        self.assertEqual(result.status_code,302,result.content)
        run=other.port.runs.first();item=run.items.get()
        _,synth=self.process(item,response(word='En katt sover.',meaning='Un chat dort.',category=''))
        self.assertFalse(synth.called)
        entry=self.save(item);self.assertEqual(entry.word,'En katt sover.')

    def test_cancelled_receipt_never_restarts_work(self):
        self.new_sentence();token=self.offer()['approval']
        with patch('community_dictionary.port_tasks.dispatch'),self.captureOnCommitCallbacks(execute=True):
            self.assertEqual(self.submit(token).status_code,302)
        run=self.port.runs.first();porting.cancel(self.owner,run.pk)
        with patch('community_dictionary.port_tasks.dispatch') as dispatch:
            self.assertEqual(self.submit(token).status_code,302)
        dispatch.assert_not_called()
        self.assertEqual(self.offer()['kind'],'sentences')
