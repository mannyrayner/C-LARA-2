"""Porting boundaries: paid approval, durable jobs, source custody and updates."""
from datetime import timedelta
from decimal import Decimal
import io
import json
from types import SimpleNamespace
from unittest.mock import patch
import uuid
import wave

from django.test import TestCase, Client, override_settings
from django.urls import reverse
from django.utils import timezone

from community_dictionary import port_ai, porting, port_tasks
from community_dictionary.models import (Contribution, ContributionDependency, Dictionary, Entry,
    LanguagePort, PortEntryLink, PortItem, PortRun)
from community_dictionary.participation import withdraw_all, restore_all
from community_dictionary.services import Conflict, add_contributions
from community_dictionary.storage import path_for
from projects.models import CreditAccount, CreditLedgerEntry, AIUsageCharge, Profile
from . import test_workflow as workflow


def response(word='gatto',meaning='cat',category='Home',outcome='candidate',**extra):
    return SimpleNamespace(status='completed',output_text=json.dumps(dict(outcome=outcome,word=word,
        meaning=meaning,category=category,feedback=extra.pop('feedback',''),category_language=extra.pop('category_language','commenting'),**extra)),
        usage=SimpleNamespace(input_tokens=1200,output_tokens=100))


def speech(*args,**kwargs):
    data = io.BytesIO()
    with wave.open(data,'wb') as out:
        out.setparams((1,2,8000,0,'NONE','not compressed'))
        out.writeframes(b'\x01\x02'*8000)
    return (data.getvalue(),'audio/wav','.wav'),1.0


@override_settings(OPENAI_API_KEY='fixture-only', CREDITS_ENABLED=True,
    COMMUNITY_DICTIONARY_PHOTO_MODEL='gpt-6-sol', COMMUNITY_DICTIONARY_PORT_WINDOW=2)
class PortingTests(TestCase):
    setUp = workflow.WorkflowTests.setUp
    url = workflow.WorkflowTests.url
    post = workflow.WorkflowTests.post
    create_entry = workflow.WorkflowTests.create_entry

    def seed(self,word='katt',meaning='cat',author=None):
        self.dictionary.explanation_language='English';self.dictionary.save()
        self.client.force_login(author or self.owner)
        entry=self.create_entry(word=word,meaning=meaning,category='Home',audio=workflow.recording(),publish_now='on')
        if author:
            # Ordinary member's proposals require an editor's acceptance.
            from community_dictionary.services import accept
            for part in entry.contributions.filter(status='pending'):
                accept(part,self.owner)
        return entry

    def quote(self,language='Italian',explanation='English',port=None):
        self.client.force_login(self.owner)
        return porting.quote(self.owner,self.dictionary,dict(name='New version',language=language,
            explanation_language=explanation,voice='marin'),uuid.uuid4(),port=port)

    def approve(self,run,balance='5'):
        CreditAccount.objects.update_or_create(user=self.owner,defaults={'balance_usd':Decimal(balance)})
        with patch('community_dictionary.port_tasks.send') as send, self.captureOnCommitCallbacks(execute=True):
            run=porting.approve(self.owner,run.pk)
        run.refresh_from_db()
        return run

    def process(self,item,answer=None):
        with patch.object(port_ai,'translate',return_value=answer or response()) as translate, \
             patch('community_dictionary.tts.synthesize',side_effect=speech) as synthesize, \
             patch('community_dictionary.port_tasks.send'), self.captureOnCommitCallbacks(execute=True):
            port_tasks.process_item(item.pk)
        item.refresh_from_db()
        return translate,synthesize

    def save(self,item,**extra):
        item.refresh_from_db()
        return porting.save_item(self.owner,item.pk,{**item.result,**extra})

    def test_quote_is_free_private_and_explicit_approval_required(self):
        self.seed()
        with patch.object(port_ai,'translate') as call:
            run=self.quote()
            self.assertFalse(call.called)
        self.assertIsNone(run.port.destination_id)
        self.assertEqual(run.items.count(),1)
        self.assertGreater(run.allowance_usd,run.estimated_usd)
        page=self.client.get(reverse('community_dictionary:port-run',args=[self.dictionary.pk,run.pk]))
        self.assertContains(page,'Insufficient C-LARA credit')
        action=reverse('community_dictionary:port-action',args=[self.dictionary.pk,run.pk])
        self.assertEqual(self.client.post(action,{'action':'approve'}).status_code,400)
        self.assertEqual(self.client.post(action,{'action':'approve','approve':'on'}).status_code,409)
        self.assertFalse(CreditLedgerEntry.objects.exists())
        run.refresh_from_db();self.assertEqual(run.status,'estimate')

    def test_approval_reserves_once_and_fanin_refunds_unused_credit(self):
        source=self.seed()
        run=self.approve(self.quote()); reserved=run.allowance_usd
        self.assertEqual(CreditAccount.objects.get(user=self.owner).balance_usd,5-reserved)
        porting.approve(self.owner,run.pk)
        self.assertEqual(CreditLedgerEntry.objects.count(),1)
        item=run.items.get();self.process(item)
        run.refresh_from_db()
        self.assertTrue(run.settled);self.assertEqual(run.status,'complete')
        self.assertLess(run.charged_usd,reserved)
        self.assertEqual(CreditAccount.objects.get(user=self.owner).balance_usd,5-run.charged_usd)
        self.assertEqual(AIUsageCharge.objects.count(),2)
        with patch.object(port_ai,'translate') as again:
            port_tasks.process_item(item.pk)
            self.assertFalse(again.called)
        port_tasks.dispatch(str(run.pk));self.assertEqual(CreditLedgerEntry.objects.count(),2)
        target=self.save(item)
        self.assertEqual(target.word,'gatto');self.assertEqual(target.meaning,'cat')
        self.assertEqual(target.dictionary.language,'Italian')
        self.assertFalse(target.dictionary.memberships.exists())
        self.assertEqual(source.contributions.get(kind='image').file_path,target.contributions.get(kind='image').file_path)
        self.assertEqual(target.contributions.get(kind='audio').provenance['source_text'],'gatto')
        source.refresh_from_db();self.assertEqual(source.word,'katt')
        self.save(item);self.assertEqual(PortEntryLink.objects.count(),1)

    def test_commenting_only_preserves_original_word_audio_and_provenance(self):
        source=self.seed()
        run=self.approve(self.quote('Swedish','French'))
        item=run.items.get()
        _,tts_call=self.process(item,response('WRONG','chat','Maison'))
        self.assertFalse(tts_call.called)
        self.assertEqual(item.result['word'],'katt')
        target=self.save(item,word='ignored mutation')
        self.assertEqual((target.word,target.meaning,target.category),('katt','chat','Maison'))
        old=source.contributions.get(kind='audio');new=target.contributions.get(kind='audio')
        self.assertEqual((new.author_id,new.controlled_by_id,new.file_path,new.shared_from_id),
                         (old.author_id,old.controlled_by_id,old.file_path,old.pk))
        self.assertEqual(target.current_text.shared_from_id,source.current_text_id if source.current_text_id else source.contributions.get(text_field='word').pk)

    def test_other_language_fields_forced_unchanged_and_edited_word_discards_audio(self):
        self.seed()
        run=self.approve(self.quote());item=run.items.get()
        self.process(item,response('gatto','WRONG','WRONG'))
        self.assertEqual((item.result['meaning'],item.result['category']),('cat','Home'))
        path=item.file_path
        with self.captureOnCommitCallbacks(execute=True):
            target=self.save(item,word='il gatto')
        self.assertFalse(target.contributions.filter(kind='audio').exists())
        self.assertFalse(path_for(path).exists())

    def test_owner_only_cross_dictionary_and_csrf_boundaries(self):
        self.seed();run=self.quote()
        urls=[self.url('port-start'),self.url('port-run',run.pk),self.url('port-update',run.port_id)]
        for user in [self.member,self.outsider]:
            self.client.force_login(user)
            for url in urls:self.assertEqual(self.client.get(url).status_code,404)
        self.client.force_login(self.owner)
        self.assertEqual(self.client.get(reverse('community_dictionary:port-run',args=[999,run.pk])).status_code,404)
        c=Client(enforce_csrf_checks=True);c.force_login(self.owner)
        self.assertEqual(c.post(self.url('port-action',run.pk),{'action':'approve','approve':'on'}).status_code,403)

    def test_personal_key_disclosure_and_no_clara_charge(self):
        self.seed()
        profile,_=Profile.objects.get_or_create(user=self.owner)
        profile.use_personal_openai_key=True;profile.openai_api_key='private-fixture';profile.save()
        run=self.quote()
        self.assertEqual(run.payer,'personal')
        page=self.client.get(self.url('port-run',run.pk));self.assertContains(page,'cannot check its balance')
        run=self.approve(run,balance='0');self.process(run.items.get())
        self.assertFalse(CreditLedgerEntry.objects.exists())
        self.assertEqual(CreditAccount.objects.get(user=self.owner).balance_usd,0)

    def test_changed_settings_expiry_and_source_changes_require_new_quote(self):
        source=self.seed();run=self.quote()
        run.expires_at=timezone.now()-timedelta(seconds=1);run.save()
        with self.assertRaises(Conflict):self.approve(run)
        run=self.quote()
        add_contributions(source,self.owner,{'word':'katten','edit_text':True},[],publish=True)
        with self.assertRaises(Conflict):self.approve(run)
        run=self.quote()
        with override_settings(COMMUNITY_DICTIONARY_PHOTO_MODEL='unpriced-fixture'):
            with self.assertRaises(Conflict):self.approve(run)

    def test_fanout_window_dispatches_next_entry_and_fanin_waits_for_all(self):
        for word in ['katt','hund','häst']:self.seed(word)
        run=self.approve(self.quote())
        self.assertEqual(run.items.filter(status='queued').count(),2)
        self.assertEqual(run.items.filter(status='waiting').count(),1)
        self.process(run.items.filter(status='queued').first())
        run.refresh_from_db();self.assertFalse(run.settled)
        self.assertEqual(run.items.filter(status='queued').count(),2)
        for item in run.items.filter(status='queued'):self.process(item)
        run.refresh_from_db();self.assertTrue(run.settled)
        self.assertEqual(run.items.filter(status='ready').count(),3)

    def test_timeout_not_retried_and_other_entries_continue(self):
        self.seed();self.seed('hund')
        run=self.approve(self.quote());item=run.items.first()
        with patch.object(port_ai,'translate',side_effect=TimeoutError),patch('community_dictionary.port_tasks.send'):
            port_tasks.process_item(item.pk)
        item.refresh_from_db();self.assertEqual(item.status,'failed');self.assertTrue(item.uncertain_cost)
        self.process(run.items.exclude(pk=item.pk).get())
        run.refresh_from_db();self.assertTrue(run.settled)
        self.assertEqual(run.items.filter(status='ready').count(),1)

    def test_bad_json_still_accounts_returned_tokens(self):
        self.seed();run=self.approve(self.quote());item=run.items.get()
        bad=response();bad.output_text='not json'
        self.process(item,bad)
        self.assertEqual(item.status,'failed');self.assertGreater(item.translation_cost,0)
        self.assertEqual(AIUsageCharge.objects.count(),1)

    def test_tts_failure_preserves_text_for_review(self):
        self.seed();run=self.approve(self.quote());item=run.items.get()
        with patch.object(port_ai,'translate',return_value=response()),patch('community_dictionary.tts.synthesize',side_effect=TimeoutError):
            port_tasks.process_item(item.pk)
        item.refresh_from_db();self.assertEqual(item.status,'ready');self.assertFalse(item.file_path)
        self.assertTrue(item.uncertain_cost)
        target=self.save(item);self.assertEqual(target.word,'gatto')

    def test_unclear_result_requires_word_but_can_be_saved_manually_without_speech(self):
        self.seed();run=self.approve(self.quote());item=run.items.get()
        _,audio=self.process(item,response('','','','unclear'))
        self.assertEqual(item.status,'unclear');self.assertFalse(audio.called)
        with self.assertRaises(Conflict):self.save(item)
        target=self.save(item,word='gatto')
        self.assertEqual(target.word,'gatto')
        self.assertFalse(target.contributions.filter(kind='audio').exists())

    def test_cancel_refunds_unstarted_work_and_does_not_send(self):
        self.seed();run=self.approve(self.quote())
        porting.cancel(self.owner,run.pk)
        with patch.object(port_ai,'translate') as call:port_tasks.process_item(run.items.get().pk)
        self.assertFalse(call.called)
        self.assertEqual(CreditAccount.objects.get(user=self.owner).balance_usd,5)
        run.refresh_from_db();self.assertTrue(run.settled)

    def test_update_skips_unchanged_protects_corrections_and_adds_new_entries(self):
        source=self.seed();run=self.approve(self.quote());item=run.items.get();self.process(item)
        target=self.save(item)
        update=self.quote(port=run.port);self.assertEqual(update.items.count(),0);self.assertEqual(update.skipped,1)
        add_contributions(target,self.owner,{'word':'il gatto','edit_text':True},[],publish=True)
        add_contributions(source,self.owner,{'word':'katten','edit_text':True},[],publish=True)
        self.seed('häst','horse')
        update=self.quote(port=run.port);self.assertEqual(update.protected,1);self.assertEqual(update.items.count(),1)
        target.refresh_from_db();self.assertEqual(target.word,'il gatto')

    def test_source_edit_or_destination_edit_during_run_prevents_overwrite(self):
        source=self.seed();run=self.approve(self.quote());item=run.items.get();self.process(item)
        add_contributions(source,self.owner,{'word':'katten','edit_text':True},[],publish=True)
        with self.assertRaises(Conflict):self.save(item)
        self.assertEqual(self.client.get(self.url('port-media',run.pk,item.pk,'audio')).status_code,404)

    def test_source_withdrawal_discards_unsaved_previews_and_blocks_urls(self):
        self.seed(author=self.member);run=self.approve(self.quote());item=run.items.get();self.process(item)
        path=item.file_path
        with self.captureOnCommitCallbacks(execute=True):withdraw_all(self.member,self.dictionary.pk,0)
        item.refresh_from_db();self.assertEqual((item.result,item.file_path,item.status),({},'','discarded'))
        self.assertFalse(path_for(path).exists())
        self.assertEqual(self.client.get(self.url('port-media',run.pk,item.pk,'audio')).status_code,404)

    def test_withdrawal_moves_derived_translation_audio_and_image_then_restores(self):
        source=self.seed(author=self.member);run=self.approve(self.quote());item=run.items.get();self.process(item)
        target=self.save(item)
        self.assertTrue(ContributionDependency.objects.filter(derived__entry=target).exists())
        withdraw_all(self.member,self.dictionary.pk,0)
        target.refresh_from_db();self.assertEqual(target.word,'');self.assertFalse(target.contributions.exists())
        restore_all(self.member,self.dictionary.pk,1)
        target.refresh_from_db();self.assertEqual(target.word,'gatto')
        self.assertTrue(target.contributions.filter(kind='audio',status='accepted').exists())

    def test_source_withdrawal_inflight_discards_result_and_still_accounts_usage(self):
        self.seed(author=self.member);run=self.approve(self.quote());item=run.items.get()
        def withdraw_during(*args,**kwargs):
            withdraw_all(self.member,self.dictionary.pk,0)
            return response()
        with patch.object(port_ai,'translate',side_effect=withdraw_during),patch('community_dictionary.tts.synthesize') as audio:
            port_tasks.process_item(item.pk)
        item.refresh_from_db();run.refresh_from_db()
        self.assertEqual(item.status,'discarded');self.assertEqual(item.result,{})
        self.assertFalse(audio.called);self.assertTrue(run.settled);self.assertGreater(run.charged_usd,0)

    def test_recovery_requeues_only_unclaimed_work_and_abandons_old_paid_attempt(self):
        self.seed();self.seed('hund');run=self.approve(self.quote());item=run.items.first()
        item.status='running';item.started_at=timezone.now()-timedelta(minutes=16);item.save()
        with patch('community_dictionary.port_tasks.send') as send,self.captureOnCommitCallbacks(execute=True):
            port_tasks.resume(self.owner,run.pk)
        item.refresh_from_db();self.assertEqual(item.status,'failed');self.assertTrue(item.uncertain_cost)
        self.assertNotIn(item.pk,[c.args[0] for c in send.call_args_list])

    def test_quote_review_and_save_ui(self):
        self.seed()
        result=self.client.post(self.url('port-start'),{'submission_id':str(uuid.uuid4()),'name':'Italian test',
            'language':'Italian','explanation_language':'English','voice':'cedar'})
        self.assertEqual(result.status_code,302)
        run=PortRun.objects.latest('created_at');self.approve(run);item=run.items.get();self.process(item)
        url=self.url('port-review',run.pk,item.pk)
        self.assertContains(self.client.get(url),'gatto')
        media=self.client.get(self.url('port-media',run.pk,item.pk,'audio'))
        self.assertEqual(media.status_code,200);media.close()
        self.assertEqual(self.client.post(url,{'word':'gatto','meaning':'cat','category':'Home'}).status_code,302)
        self.assertEqual(PortEntryLink.objects.count(),1)

    def test_review_corrections_are_protected_on_future_source_updates(self):
        source=self.seed();run=self.approve(self.quote());item=run.items.get();self.process(item)
        target=self.save(item,word='il gatto')
        add_contributions(source,self.owner,{'meaning':'kitty','edit_text':True},[],publish=True)
        update=self.quote(port=run.port)
        self.assertEqual(update.protected,1);self.assertFalse(update.items.exists())
        target.refresh_from_db();self.assertEqual(target.word,'il gatto')

    def test_update_reuses_audio_when_translated_word_and_voice_still_match(self):
        source=self.seed();run=self.approve(self.quote());item=run.items.get();self.process(item)
        target=self.save(item)
        add_contributions(source,self.owner,{'meaning':'kitty','edit_text':True},[],publish=True)
        update=self.approve(self.quote(port=run.port));next_item=update.items.get()
        _,audio=self.process(next_item)
        self.assertFalse(audio.called);self.assertTrue(next_item.result['reused_audio'])
        result=self.save(next_item)
        self.assertEqual(result.pk,target.pk);self.assertEqual(result.meaning,'kitty')
        self.assertEqual(result.contributions.filter(kind='audio').count(),1)

    def test_shared_image_word_links_are_retained_and_stable_for_updates(self):
        from community_dictionary.models import ImageWordLink
        a=self.seed();b=self.seed('soffa','sofa')
        ImageWordLink.objects.create(image=a.contributions.get(kind='image'),word_entry=b,created_by=self.owner)
        run=self.approve(self.quote())
        for item in run.items.all():
            self.process(item,response('gatto' if item.source_entry_id==a.pk else 'divano'))
            self.save(item)
        links=ImageWordLink.objects.filter(word_entry__dictionary=run.port.destination)
        self.assertEqual(links.count(),2)
        update=self.quote(port=run.port);self.assertEqual(update.skipped,2);self.assertFalse(update.items.exists())

    def test_multi_source_holds_require_both_contributors_to_restore(self):
        source=self.seed(author=self.member)
        add_contributions(source,self.third,{'meaning':'kitty','edit_text':True},[],publish=False)
        from community_dictionary.services import accept
        accept(source.contributions.filter(status='pending',text_field='meaning').get(),self.owner)
        run=self.approve(self.quote());item=run.items.get();self.process(item);target=self.save(item)
        withdraw_all(self.member,self.dictionary.pk,0)
        withdraw_all(self.third,self.dictionary.pk,0)
        restore_all(self.member,self.dictionary.pk,1)
        target.refresh_from_db();self.assertEqual(target.word,'')
        restore_all(self.third,self.dictionary.pk,1)
        target.refresh_from_db();self.assertEqual(target.word,'gatto')

    def test_export_keeps_dependency_ids_without_exporting_other_dictionary(self):
        import zipfile
        self.seed();run=self.approve(self.quote());item=run.items.get();self.process(item);target=self.save(item)
        result=self.client.get(reverse('community_dictionary:export',args=[target.dictionary_id]))
        try:
            data=b''.join(result.streaming_content)
        finally:
            result.close()
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            links=json.loads(archive.read('provenance-links.json'))
            self.assertTrue(links)
            records=json.loads(archive.read('records.json'))
            self.assertEqual([r['pk'] for r in records if r['model']=='community_dictionary.dictionary'],[target.dictionary_id])

    def test_funding_is_rechecked_at_approval_and_capped_at_reserved_amount(self):
        self.seed();run=self.quote()
        CreditAccount.objects.update_or_create(user=self.owner,defaults={'balance_usd':run.allowance_usd-Decimal('.0001')})
        with self.assertRaises(Conflict):porting.approve(self.owner,run.pk)
        run=self.approve(run)
        giant=response();giant.usage.input_tokens=1000000
        self.process(run.items.get(),giant)
        run.refresh_from_db();self.assertEqual(run.charged_usd,run.reserved_usd)
        self.assertEqual(CreditAccount.objects.get(user=self.owner).balance_usd,5-run.reserved_usd)

    def test_queue_payload_is_id_only_and_compatible_with_local_shim(self):
        self.seed();run=self.approve(self.quote());item=run.items.get()
        with patch('django_q.tasks.async_task') as enqueue:
            port_tasks.send(item.pk)
        args,kwargs=enqueue.call_args
        self.assertEqual(args,('community_dictionary.port_tasks.process_item',item.pk))
        self.assertEqual(set(kwargs),{'q_options'})
        self.assertNotIn('word',repr((args,kwargs)))

    def test_cancel_inflight_accounts_current_call_but_sends_no_speech(self):
        self.seed();run=self.approve(self.quote());item=run.items.get()
        def stop(*args,**kwargs):
            porting.cancel(self.owner,run.pk)
            return response()
        with patch.object(port_ai,'translate',side_effect=stop),patch('community_dictionary.tts.synthesize') as audio:
            port_tasks.process_item(item.pk)
        item.refresh_from_db();run.refresh_from_db()
        self.assertEqual(item.status,'discarded');self.assertFalse(audio.called)
        self.assertEqual(run.status,'cancelled');self.assertTrue(run.settled)
        self.assertGreater(run.charged_usd,0)

    def test_target_language_category_uses_examples_and_preserves_source(self):
        source=self.seed()
        add_contributions(source,self.owner,{'category':'djur','edit_text':True},[],publish=True)
        self.seed('hund','dog')
        second=Entry.objects.get(dictionary=self.dictionary,word='hund')
        add_contributions(second,self.owner,{'category':'djur','edit_text':True},[],publish=True)
        run=self.approve(self.quote(language='French'))
        item=run.items.get(source_entry=source)
        translate,audio=self.process(item,response('chat',category='animaux',category_language='target'))
        sent=translate.call_args.args[0]
        self.assertEqual({e['word'] for e in sent['category_examples']},{'katt','hund'})
        self.assertEqual(audio.call_args.kwargs['language'],'fr')
        target=self.save(item)
        self.assertEqual((target.word,target.meaning,target.category),('chat','cat','animaux'))
        source.refresh_from_db();self.assertEqual(source.category,'djur')
        self.assertEqual(target.current_category.provenance['origin'],'language-port')
        self.assertTrue(ContributionDependency.objects.filter(source=second.current_text,derived=target.current_category).exists())

    def test_commenting_category_is_unchanged_when_only_target_changes(self):
        source=self.seed();run=self.approve(self.quote(language='French'));item=run.items.get()
        self.process(item,response('chat',category='Maison',category_language='commenting'))
        self.assertEqual(item.result['category'],'Home')
        target=self.save(item)
        self.assertEqual(target.current_category.shared_from_id,source.current_category_id)
        self.assertEqual(target.current_category.author_id,source.current_category.author_id)

    def test_commenting_only_port_classifies_categories_independently(self):
        a=self.seed();b=self.seed('hund','dog')
        add_contributions(b,self.owner,{'category':'djur','edit_text':True},[],publish=True)
        run=self.approve(self.quote(language=self.dictionary.language,explanation='French'))
        first=run.items.get(source_entry=a)
        self.process(first,response('wrong','chat','Maison',category_language='commenting'))
        second=run.items.get(source_entry=b)
        self.process(second,response('wrong','chien','animaux',category_language='target'))
        self.assertEqual(self.save(first).category,'Maison')
        target=self.save(second)
        self.assertEqual((target.word,target.meaning,target.category),('hund','chien','djur'))

    def test_shared_category_decision_is_consistent_and_cached_for_updates(self):
        a=self.seed();b=self.seed('hund','dog')
        for entry in [a,b]:add_contributions(entry,self.owner,{'category':'djur','edit_text':True},[],publish=True)
        run=self.approve(self.quote(language='French'))
        first=run.items.get(source_entry=a);second=run.items.get(source_entry=b)
        self.process(first,response('chat',category='animaux',category_language='target'))
        # Simulate a concurrently issued call returning a different classification.
        self.process(second,response('chien',category='bêtes',category_language='commenting'))
        self.assertEqual(second.result['category'],'animaux')
        self.assertEqual(second.result['category_language'],'target')
        self.save(first);self.save(second)
        update=self.quote(port=run.port)
        self.assertEqual(update.skipped,2)
        self.assertEqual(next(iter(update.category_plan.values()))['decision']['category'],'animaux')

    def test_uncertain_category_is_preserved_but_editable(self):
        self.seed();run=self.approve(self.quote());item=run.items.get()
        self.process(item,response(category='guessed',category_language='uncertain'))
        self.assertEqual(item.result['category'],'Home')
        url=self.url('port-review',run.pk,item.pk)
        self.assertContains(self.client.get(url),'category’s language is uncertain')
        self.assertEqual(self.client.post(url,{'word':'gatto','meaning':'cat','category':'Casa'}).status_code,302)
        link=PortEntryLink.objects.get(source=item.source_entry)
        self.assertEqual(link.destination.category,'Casa');self.assertTrue(link.manually_edited)

    def test_category_context_change_blocks_stale_approval(self):
        self.seed();example=self.seed('hund','dog')
        run=self.quote();item=run.items.first()
        add_contributions(example,self.owner,{'meaning':'hound','edit_text':True},[],publish=True)
        with self.assertRaises(Conflict):porting.current_item(item)
        with self.assertRaises(Conflict):self.approve(run)

    def test_category_example_withdrawal_invalidates_previews_and_saved_derivatives(self):
        source=self.seed();example=self.seed('hund','dog',author=self.member)
        run=self.approve(self.quote());item=run.items.get(source_entry=source)
        self.process(item);target=self.save(item)
        other=run.items.get(source_entry=example);self.process(other)
        withdraw_all(self.member,self.dictionary.pk,0)
        other.refresh_from_db();run.refresh_from_db();target.refresh_from_db()
        self.assertEqual(other.status,'discarded');self.assertEqual(other.result,{})
        self.assertIsNone(next(iter(run.category_plan.values()))['decision'])
        self.assertEqual(target.word,'')
        restore_all(self.member,self.dictionary.pk,1)
        target.refresh_from_db();self.assertEqual(target.word,'gatto')

    def test_unclear_legacy_preview_can_be_overridden_without_changing_source(self):
        source=self.seed('kung','king');run=self.approve(self.quote(language='French'));item=run.items.get()
        # Existing previews created before the schema change had empty text fields.
        item.status='unclear';item.result=dict(outcome='unclear',word='',meaning='',category='',feedback='Image mismatch')
        item.save()
        url=self.url('port-review',run.pk,item.pk)
        page=self.client.get(url)
        self.assertContains(page,'enter your own')
        self.assertEqual(page.context['form'].initial['meaning'],'king')
        self.assertEqual(page.context['form'].initial['category'],'Home')
        self.assertEqual(self.client.post(url,{'word':'roi','meaning':'king','category':'Home'}).status_code,302)
        target=PortEntryLink.objects.get(source=source).destination
        self.assertEqual((target.word,target.meaning),('roi','king'))
        self.assertEqual(target.contributions.filter(kind='image').count(),1)
        source.refresh_from_db();self.assertEqual(source.word,'kung')
        self.assertFalse(target.contributions.filter(kind='audio').exists())

    def test_tentative_suggestion_can_be_accepted_without_a_veto(self):
        self.seed('kung','king');run=self.approve(self.quote(language='French'));item=run.items.get()
        _,audio=self.process(item,response('roi','king',outcome='unclear',feedback='Please check the picture.'))
        self.assertEqual(item.result['word'],'roi');self.assertFalse(audio.called)
        target=self.save(item);self.assertEqual(target.word,'roi')

    def test_old_recipe_update_regenerates_audio_without_duplicate_playable_recordings(self):
        from community_dictionary import tts
        source=self.seed();run=self.approve(self.quote(language='French'));item=run.items.get()
        self.process(item,response('chat'));target=self.save(item)
        old=target.contributions.get(kind='audio')
        old.provenance.pop('instructions_version');old.save()
        link=PortEntryLink.objects.get(source=source)
        link.source_digest=porting.snapshot(source)['digest']  # first-release digest
        link.destination_digest=porting.snapshot(target)['digest'];link.save()
        update=self.approve(self.quote(port=run.port));next_item=update.items.get()
        _,audio=self.process(next_item,response('chat'));self.assertTrue(audio.called)
        self.save(next_item);old.refresh_from_db()
        self.assertEqual(old.status,'superseded')
        recording=target.contributions.get(kind='audio',status='accepted')
        self.assertEqual(recording.provenance['instructions_version'],tts.INSTRUCTIONS_VERSION)
        self.assertNotEqual(old.pk,recording.pk)

    def test_french_language_reaches_real_tts_engine_request_on_both_sdk_paths(self):
        from unittest.mock import MagicMock
        from pathlib import Path
        from community_dictionary import tts
        data,_=speech()
        for streaming in [True,False]:
            with self.subTest(streaming=streaming):
                response_mock=MagicMock()
                response_mock.stream_to_file.side_effect=lambda path:Path(path).write_bytes(data[0])
                create=MagicMock(return_value=MagicMock(__enter__=lambda _:response_mock,__exit__=lambda *args:False) if streaming else response_mock)
                speech_client=SimpleNamespace(with_streaming_response=SimpleNamespace(create=create) if streaming else None, create=create)
                client=SimpleNamespace(audio=SimpleNamespace(speech=speech_client))
                with patch.object(tts,'_openai_client') as factory:
                    factory.return_value.__enter__.return_value=client
                    prepared,duration=tts.synthesize('fromage',language='fr',model=tts.MODEL,voice='marin',api_key='test-only')
                payload=create.call_args.kwargs
                self.assertEqual(payload['input'],'fromage')
                self.assertEqual(payload['voice'],'marin')
                self.assertIn('français de France',payload['instructions'])
                self.assertIn('prononciation française naturelle',payload['instructions'])
                self.assertEqual(prepared[1],'audio/wav');self.assertGreater(duration,0)

    def test_strict_tts_does_not_drop_language_instruction_on_sdk_error(self):
        from unittest.mock import MagicMock
        from community_dictionary import tts
        create=MagicMock(side_effect=TypeError('instructions unsupported'))
        client=SimpleNamespace(audio=SimpleNamespace(speech=SimpleNamespace(with_streaming_response=None,create=create)))
        with patch.object(tts,'_openai_client') as factory:
            factory.return_value.__enter__.return_value=client
            with self.assertRaises(TypeError):
                tts.synthesize('fromage',language='fr',model=tts.MODEL,voice='marin',api_key='test-only')
        self.assertEqual(create.call_count,1)

    def test_saving_pre_upgrade_preview_does_not_relabel_old_speech_as_new(self):
        source=self.seed();run=self.approve(self.quote(language='French'));item=run.items.get()
        self.process(item,response('chat'))
        for field in ['recipe','tts_instructions_version','category_language']:
            item.result.pop(field,None)
        item.save(update_fields=['result'])
        run.category_plan={};run.save(update_fields=['category_plan'])
        target=self.save(item)
        old=target.contributions.get(kind='audio')
        self.assertEqual(old.provenance['instructions_version'],'')
        self.assertEqual(PortEntryLink.objects.get(source=source).source_digest,porting.snapshot(source)['digest'])
        update=self.quote(port=run.port)
        self.assertEqual(update.items.count(),1)

    def test_changing_shared_category_basis_reoffers_all_affected_entries(self):
        a=self.seed();b=self.seed('hund','dog')
        run=self.approve(self.quote())
        for entry in [a,b]:
            item=run.items.get(source_entry=entry);self.process(item);self.save(item)
        picture=Contribution.objects.create(entry=a,author=self.owner,kind='image',status='accepted',
            file_path=a.contributions.get(kind='image').file_path,mime_type='image/png')
        a.selected_image=picture;a.save(update_fields=['selected_image'])
        update=self.quote(port=run.port)
        self.assertEqual(update.items.count(),2)
        self.assertIsNone(next(iter(update.category_plan.values()))['decision'])
