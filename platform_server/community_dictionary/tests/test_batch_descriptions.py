"""Batch image -> reviewed sentence -> shared vocabulary, with no provider calls."""
from datetime import timedelta
from decimal import Decimal
import json
from types import SimpleNamespace
from unittest.mock import patch
import uuid
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from community_dictionary import batch_descriptions as batch, porting, port_tasks, port_vocabulary as vocab, port_vocabulary_tasks as jobs
from community_dictionary.models import Contribution, Dictionary, Entry, PortItem, SentenceWord
from community_dictionary.participation import withdraw_all, restore_all
from community_dictionary.services import add_contributions, Conflict
from community_dictionary.storage import prepare_upload, path_for
from projects.models import CreditAccount
from . import test_workflow as workflow
from . import test_porting as port_tests
from .test_porting import speech


def description(sentence='Katten ligger på soffan.',translation='The cat lies on the sofa.',outcome='ready'):
    return SimpleNamespace(status='completed',output_text=json.dumps(dict(outcome=outcome,
        sentence=sentence,translation=translation,feedback='A cat on the sofa.')),
        usage=SimpleNamespace(input_tokens=1000,output_tokens=150))

WORDS=[{'lemma':'katt','meaning':'cat','surface':'Katten','existing_id':0},
       {'lemma':'soffa','meaning':'sofa','surface':'soffan','existing_id':0}]


@override_settings(OPENAI_API_KEY='fixture-only',CREDITS_ENABLED=False,COMMUNITY_DICTIONARY_PORT_WINDOW=2)
class BatchDescriptionTests(TestCase):
    url=workflow.WorkflowTests.url
    post=workflow.WorkflowTests.post
    create_entry=workflow.WorkflowTests.create_entry
    approve=port_tests.PortingTests.approve

    def setUp(self):
        workflow.WorkflowTests.setUp(self)
        self.dictionary.explanation_language='English';self.dictionary.sentence_capture_enabled=True
        self.dictionary.save();self.client.force_login(self.owner)

    def picture(self,pending=False,**hints):
        self.client.force_login(self.member if pending else self.owner)
        entry=self.create_entry(**hints,**({} if pending else {'publish_now':'on'}))
        self.client.force_login(self.owner)
        return entry

    def quote(self,**kwargs):
        return batch.quote(self.owner,self.dictionary,kwargs.pop('token',uuid.uuid4()),**kwargs)

    def process(self,run,answer=None):
        with patch.object(batch,'interpret',return_value=answer or description()) as api, \
             patch('community_dictionary.tts.synthesize',side_effect=speech) as synth, \
             patch('community_dictionary.port_tasks.send'),self.captureOnCommitCallbacks(execute=True):
            for item in run.items.all():port_tasks.process_item(item.pk)
        run.refresh_from_db()
        return api,synth

    def save(self,item,**values):
        item.refresh_from_db()
        return porting.save_item(self.owner,item.pk,{**item.result,**values})

    def test_quote_is_local_defaults_both_and_does_not_create_dictionary(self):
        self.picture();self.picture(pending=True)
        with patch.object(batch,'interpret') as api,patch('community_dictionary.tts.synthesize') as speech_api:
            run=self.quote();self.assertFalse(api.called);self.assertFalse(speech_api.called)
        self.assertEqual(run.items.count(),2);self.assertEqual(Dictionary.objects.count(),1)
        self.assertGreater(run.estimated_usd,0);self.assertGreater(run.allowance_usd,run.estimated_usd)
        self.assertIsNone(run.port.destination_id);self.assertEqual(run.port.target,self.dictionary)
        self.assertEqual(self.quote(image_status='accepted').items.count(),1)
        self.assertEqual(self.quote(image_status='pending').items.count(),1)

    def test_distinct_images_on_one_entry_get_distinct_jobs(self):
        entry=self.picture()
        add_contributions(entry,self.owner,{'prepared_photo':prepare_upload(workflow.picture(),'image')},[],publish=True)
        run=self.quote();self.assertEqual(run.items.count(),2)
        run=self.approve(run);self.process(run)
        first,second=list(run.items.all())
        a=self.save(first);b=self.save(second)
        self.assertNotEqual(a.pk,b.pk);self.assertEqual(self.quote().items.count(),0)

    def test_word_label_is_a_hint_not_a_sentence_and_author_is_preserved(self):
        entry=self.picture(pending=True,meaning='Our cat on the sofa')
        original=entry.contributions.get(kind='image');hint=entry.contributions.get(text_field='meaning')
        run=self.approve(self.quote());api,synth=self.process(run)
        data=api.call_args.args[1]
        self.assertEqual(data['contributor_hints'],[{'field':'meaning','text':'Our cat on the sofa','status':'pending'}])
        self.assertEqual(synth.call_args.kwargs['speech_kind'],'sentence')
        item=run.items.get();sentence=self.save(item)
        self.assertEqual(sentence.entry_type,'sentence');self.assertEqual(sentence.word,'Katten ligger på soffan.')
        self.assertEqual(Dictionary.objects.count(),1)
        copy=sentence.contributions.get(kind='image');self.assertEqual(copy.author,self.member)
        self.assertEqual(copy.shared_from_id,original.pk);original.refresh_from_db();self.assertEqual(original.status,'accepted')
        hint.refresh_from_db();self.assertEqual(hint.status,'pending')
        self.assertTrue(sentence.current_text.source_dependencies.filter(source=hint).exists())
        self.assertTrue(sentence.contributions.filter(kind='audio',status='accepted').exists())
        self.assertEqual(self.save(item).pk,sentence.pk)
        self.assertEqual(self.quote().items.count(),0)

    def test_only_missing_pictures_are_added_on_incremental_run(self):
        entry=self.picture(word='katt',meaning='cat')
        run=self.approve(self.quote());self.process(run);sentence=self.save(run.items.get())
        self.picture();again=self.quote()
        self.assertEqual(again.items.count(),1);self.assertGreaterEqual(again.skipped,1)
        entry.refresh_from_db();self.assertEqual(entry.word,'katt')
        self.assertEqual(sentence.word,'Katten ligger på soffan.')

    def test_ready_previews_are_kept_on_incremental_run(self):
        self.picture();run=self.approve(self.quote());self.process(run)
        item=run.items.get();path=item.file_path
        self.picture();again=self.quote()
        self.assertEqual(again.items.count(),1);self.assertEqual(again.protected,1)
        item.refresh_from_db();self.assertEqual(item.status,'ready');self.assertTrue(path_for(path).exists())
        self.save(item)

    def test_preexisting_accepted_or_pending_sentence_is_skipped(self):
        entry=self.picture(pending=True,word='Katten ligger här.')
        entry.entry_type='sentence';entry.save(update_fields=['entry_type'])
        self.assertEqual(self.quote().items.count(),0)

    def test_source_edits_invalidate_estimate_and_running_result(self):
        entry=self.picture(meaning='cat');run=self.quote()
        add_contributions(entry,self.owner,{'meaning':'dog','edit_text':True},[],publish=True)
        with self.assertRaises(Conflict):self.approve(run)
        run=self.approve(self.quote());self.process(run)
        add_contributions(entry,self.owner,{'word':'hund','edit_text':True},[],publish=True)
        with self.assertRaises(Conflict):self.save(run.items.get())

    def test_sentence_added_after_quote_prevents_duplicate(self):
        entry=self.picture();run=self.quote()
        entry.entry_type='sentence';entry.save(update_fields=['entry_type'])
        add_contributions(entry,self.owner,{'word':'En katt.'},[],publish=True)
        with self.assertRaises(Conflict):self.approve(run)

    def test_edit_sentence_discards_old_audio_and_stage_two_uses_final_wording(self):
        self.picture();run=self.approve(self.quote());self.process(run)
        sentence=self.save(run.items.get(),word='Katten sitter på soffan.')
        self.assertFalse(sentence.contributions.filter(kind='audio').exists())
        second=self.approve(vocab.quote(self.owner,run.port,uuid.uuid4()))
        item=second.items.get();self.assertEqual(vocab.input_data(item)['sentence'],sentence.word)
        self.assertEqual(vocab.input_data(item)['target_language'],'Swedish')

    def test_two_stage_bulk_review_shares_words_audio_and_preserves_sentence_audio(self):
        self.picture();self.picture();run=self.approve(self.quote());self.process(run)
        with patch.object(batch,'interpret') as api:
            self.assertEqual(porting.accept_remaining(self.owner,run.pk),(2,0));self.assertFalse(api.called)
        self.assertEqual(self.dictionary.entries.filter(entry_type='sentence').count(),2)
        second=self.approve(vocab.quote(self.owner,run.port,uuid.uuid4()))
        answer=SimpleNamespace(status='completed',output_text=json.dumps({'words':WORDS}),usage=SimpleNamespace(input_tokens=900,output_tokens=100))
        with patch('community_dictionary.port_vocabulary_ai.analyse',return_value=answer),patch('community_dictionary.port_tasks.send'),self.captureOnCommitCallbacks(execute=True):
            for item in second.items.all():jobs.process_item(item.pk)
        with patch.object(jobs,'send_speech'),self.captureOnCommitCallbacks(execute=True):
            self.assertEqual(porting.accept_remaining(self.owner,second.pk),(2,0))
        self.assertEqual(second.speech.count(),2);self.assertEqual(SentenceWord.objects.count(),4)
        with patch('community_dictionary.tts.synthesize',side_effect=speech),patch.object(jobs,'send_speech'),self.captureOnCommitCallbacks(execute=True):
            for clip in second.speech.all():jobs.speak(clip.pk)
        second.refresh_from_db();self.assertTrue(second.settled)
        self.assertEqual(vocab.quote(self.owner,run.port,uuid.uuid4()).items.count(),0)
        self.assertEqual(Contribution.objects.filter(kind='audio',status='accepted').count(),4)

    def test_sentence_review_required_before_vocabulary_but_flagged_can_wait(self):
        self.picture();run=self.approve(self.quote());self.process(run)
        with self.assertRaises(Conflict):vocab.quote(self.owner,run.port,uuid.uuid4())
        run.items.update(needs_attention=True)
        self.assertEqual(vocab.quote(self.owner,run.port,uuid.uuid4()).items.count(),0)

    def test_owner_only_routes_and_same_dictionary_review_editing(self):
        self.picture()
        self.client.force_login(self.member)
        self.assertEqual(self.client.get(self.url('batch-descriptions')).status_code,404)
        self.assertEqual(self.client.post(self.url('rename'),{'name':'No'}).status_code,404)
        self.client.force_login(self.owner)
        page=self.client.get(self.url('batch-descriptions'));self.assertContains(page,'Accepted and awaiting review')
        run=self.approve(self.quote());self.process(run);item=run.items.get()
        page=self.client.get(self.url('port-review',run.pk,item.pk))
        self.assertContains(page,'Sentence');self.assertNotContains(page,'disabled')
        media=self.client.get(self.url('port-media',run.pk,item.pk,'audio'));self.assertEqual(media.status_code,200);media.close()
        post=self.client.post(self.url('port-review',run.pk,item.pk),{'word':'En katt sitter här.','meaning':'A cat sits here.','category':'','action':'save'})
        self.assertEqual(post.status_code,302)
        self.assertEqual(self.dictionary.entries.get(entry_type='sentence').word,'En katt sitter här.')
        self.assertContains(self.client.get(self.url('port-run',run.pk)),'En katt sitter här.')

    def test_rename_isolated_from_other_settings_and_counts_only_published_text(self):
        self.picture(word='katt');self.picture(pending=True,word='hund');self.picture()
        sentence=Entry.objects.create(dictionary=self.dictionary,created_by=self.owner,entry_type='sentence')
        add_contributions(sentence,self.owner,{'word':'En katt.'},[],publish=True)
        response=self.client.post(self.url('rename'),{'name':'Our pictures'})
        self.assertEqual(response.status_code,302);self.dictionary.refresh_from_db()
        self.assertEqual(self.dictionary.name,'Our pictures');self.assertEqual(self.dictionary.language,'Swedish')
        self.assertTrue(self.dictionary.sentence_capture_enabled)
        self.assertEqual(self.client.post(self.url('rename'),{'name':'  '}).status_code,400)
        home=self.client.get(reverse('community_dictionary:home'))
        self.assertContains(home,'1 sentence · 1 word')
        self.assertContains(self.client.get(self.url('settings')),'Rename dictionary')
        self.assertContains(self.client.get(self.url('settings')),'Add missing sentences')

    def test_withdrawal_invalidates_previews_and_hides_derived_sentence(self):
        self.picture(pending=True,meaning='cat');run=self.approve(self.quote());self.process(run)
        item=run.items.get();sentence=self.save(item)
        with patch('community_dictionary.port_tasks.send'),self.captureOnCommitCallbacks(execute=True):
            withdraw_all(self.member,self.dictionary.pk,0)
        sentence.refresh_from_db();self.assertFalse(sentence.current_text and sentence.current_text.status=='accepted')
        self.assertIsNone(batch.saved_entry(item))

    def test_withdrawal_during_generation_discards_result(self):
        self.picture(pending=True);run=self.approve(self.quote());item=run.items.get()
        def response(*args,**kwargs):
            withdraw_all(self.member,self.dictionary.pk,0)
            return description()
        with patch.object(batch,'interpret',side_effect=response),patch('community_dictionary.tts.synthesize') as synth,patch('community_dictionary.port_tasks.send'),self.captureOnCommitCallbacks(execute=True):
            port_tasks.process_item(item.pk)
        item.refresh_from_db();self.assertEqual(item.status,'discarded');self.assertFalse(synth.called)

    @override_settings(CREDITS_ENABLED=True)
    def test_cost_approval_and_idempotency(self):
        self.picture();token=uuid.uuid4();run=self.quote(token=token)
        self.assertEqual(self.quote(token=token).pk,run.pk)
        CreditAccount.objects.update_or_create(user=self.owner,defaults={'balance_usd':0})
        with self.assertRaises(Conflict):porting.approve(self.owner,run.pk)
        page=self.client.get(self.url('port-run',run.pk));self.assertContains(page,'Insufficient C-LARA credit')
        run=self.approve(run,balance='100');self.process(run)
        with patch.object(batch,'interpret') as api:
            porting.approve(self.owner,run.pk);port_tasks.process_item(run.items.get().pk);self.assertFalse(api.called)
        run.refresh_from_db();self.assertTrue(run.settled)
        self.assertEqual(CreditAccount.objects.get(user=self.owner).balance_usd,Decimal(100)-run.charged_usd)

    def test_timeout_is_not_retried_and_expired_claim_recovery_is_safe(self):
        self.picture();run=self.approve(self.quote());item=run.items.get()
        with patch.object(batch,'interpret',side_effect=TimeoutError) as api,patch('community_dictionary.port_tasks.send'),self.captureOnCommitCallbacks(execute=True):
            port_tasks.process_item(item.pk);port_tasks.process_item(item.pk)
        self.assertEqual(api.call_count,1);item.refresh_from_db();self.assertTrue(item.uncertain_cost)
        self.assertEqual(item.status,'failed')
        next_run=self.approve(self.quote());next_item=next_run.items.get()
        next_item.status='running';next_item.started_at=timezone.now()-timedelta(minutes=20);next_item.save()
        with patch.object(batch,'interpret') as api,patch('community_dictionary.port_tasks.send'),self.captureOnCommitCallbacks(execute=True):
            port_tasks.resume(self.owner,next_run.pk)
        next_item.refresh_from_db();self.assertEqual(next_item.status,'failed');self.assertFalse(api.called)

    def test_cancel_keeps_saved_sentences_and_deletes_private_previews(self):
        self.picture();self.picture();run=self.approve(self.quote());self.process(run)
        a,b=list(run.items.all());saved=self.save(a);path=b.file_path
        with self.captureOnCommitCallbacks(execute=True):porting.cancel(self.owner,run.pk)
        self.assertTrue(Entry.objects.filter(pk=saved.pk).exists());self.assertFalse(path_for(path).exists())
        b.refresh_from_db();self.assertEqual(b.status,'discarded')

    def test_feature_disabled_and_revoked_membership_stop_processing(self):
        self.picture();run=self.approve(self.quote());self.dictionary.sentence_capture_enabled=False;self.dictionary.save()
        with patch.object(batch,'interpret') as api,patch('community_dictionary.port_tasks.send'),self.captureOnCommitCallbacks(execute=True):
            port_tasks.process_item(run.items.get().pk)
        self.assertFalse(api.called);self.assertEqual(run.items.get().status,'discarded')

    def test_batch_on_language_port_destination_preserves_its_original_port(self):
        self.picture();source=Dictionary.objects.create(owner=self.owner,name='Original',language='French')
        from community_dictionary.models import LanguagePort
        port=LanguagePort.objects.create(source=source,destination=self.dictionary,user=self.owner,name='Version',language='Swedish',explanation_language='English')
        run=self.approve(self.quote());self.process(run);self.save(run.items.get())
        self.dictionary.refresh_from_db();self.assertEqual(self.dictionary.language_port.pk,port.pk)
        self.assertEqual(Dictionary.objects.count(),2)

    def test_stale_unsaved_preview_can_be_reestimated_without_repeating_valid_ones(self):
        entry=self.picture(meaning='cat');run=self.approve(self.quote());self.process(run)
        add_contributions(entry,self.owner,{'meaning':'our cat','edit_text':True},[],publish=True)
        with self.captureOnCommitCallbacks(execute=True):again=self.quote()
        self.assertEqual(again.items.count(),1);self.assertEqual(run.items.get().status,'discarded')

    def test_expired_individual_preview_does_not_block_batch(self):
        from community_dictionary.models import PictureCapture
        entry=self.picture();image=entry.contributions.get(kind='image')
        preview=PictureCapture.objects.create(dictionary=self.dictionary,user=self.owner,source_image=image,
            language='Swedish',explanation_language='English',input_language='English',model='fixture',status='ready',
            expires_at=timezone.now()+timedelta(hours=1))
        self.assertEqual(self.quote().items.count(),0)
        preview.expires_at=timezone.now()-timedelta(seconds=1);preview.save()
        self.assertEqual(self.quote().items.count(),1)

    def test_withdrawn_member_cannot_see_dictionary_counts(self):
        self.picture(word='katt')
        withdraw_all(self.member,self.dictionary.pk,0)
        self.client.force_login(self.member)
        page=self.client.get(reverse('community_dictionary:home'))
        self.assertContains(page,'Your content is withdrawn');self.assertNotContains(page,'dictionary-counts')

    def test_vocabulary_preview_uses_same_dictionary_links(self):
        self.picture();run=self.approve(self.quote());self.process(run);sentence=self.save(run.items.get())
        second=self.approve(vocab.quote(self.owner,run.port,uuid.uuid4()));item=second.items.get()
        item.status='ready';item.result={'words':WORDS};item.save()
        page=self.client.get(self.url('port-review',second.pk,item.pk))
        self.assertContains(page,self.url('entry',sentence.pk));self.assertContains(page,'Open sentence and listen')

    @override_settings(COMMUNITY_DICTIONARY_CAPTURE_DAILY_LIMIT=0)
    def test_server_pause_blocks_batch(self):
        self.picture()
        with self.assertRaises(Conflict):self.quote()

    def test_copied_generated_image_keeps_original_provenance(self):
        entry=self.picture();image=entry.contributions.get(kind='image')
        image.provenance={'origin':'ai-generated','model':'original-model'};image.save()
        run=self.approve(self.quote());self.process(run);sentence=self.save(run.items.get())
        copied=sentence.contributions.get(kind='image')
        self.assertEqual(copied.provenance['origin'],'ai-generated')
        self.assertEqual(copied.provenance['model'],'original-model')
