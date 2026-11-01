"""Offline replacement, stale data, custody and credit contracts."""
import uuid
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch
from django.test import TestCase, Client, override_settings
from django.urls import reverse
from django.utils import timezone
from community_dictionary import audio_review as review, homograph_experiments as exp, port_tasks, porting, sentence_forms as sf
from community_dictionary.collections import dependent_ids
from community_dictionary.models import Contribution, SentenceWord
from community_dictionary.participation import withdraw_all
from community_dictionary.services import Conflict
from community_dictionary.storage import write_upload, path_for
from projects.models import CreditAccount, CreditLedgerEntry
from . import test_homograph_experiments as fixtures
from .test_mwe_audio import carrier_wave
from .test_tts_guidance import provider

@override_settings(OPENAI_API_KEY='fixture-only', CREDITS_ENABLED=True,
    COMMUNITY_DICTIONARY_PORT_WINDOW=2, PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class ReviewTests(TestCase):
    setUp=fixtures.ExperimentTests.setUp
    seed=fixtures.ExperimentTests.seed
    approve=fixtures.ExperimentTests.approve
    synthesis=staticmethod(fixtures.ExperimentTests.synthesis)
    finish=fixtures.ExperimentTests.finish

    def url(self,name='',*args):
        return reverse('community_dictionary:audio-review'+('-'+name if name else ''),args=[self.dictionary.pk,*args])

    def old_audio(self,entry,part=None,human=False):
        part=part or entry.current_text
        provenance={'origin':'human' if human else 'synthetic','source_text':part.word,
            'source_text_id':part.pk,'language':self.dictionary.language,'voice':'marin'}
        if part.kind=='form':provenance['sentence_form']=part.pk
        return Contribution.objects.create(entry=entry,author=self.owner,shared_from=part,kind='audio',
            status='accepted',provenance=provenance,**write_upload((carrier_wave(),'audio/wav','.wav'),self.dictionary.pk,[]))

    def mark(self,part,decision='replace'):
        row=review.live_row(self.dictionary,part.pk)
        old,previous=review.decisions(self.owner,self.dictionary).get(part.pk,(None,''))
        review.mark(self.owner,self.dictionary,part.pk,review.fingerprint(row),previous if old==row else '',decision)

    def quote(self,entries=None):
        for entry in entries or [self.seed()]:self.mark(entry.current_text)
        return review.quote(self.owner,self.dictionary,uuid.uuid4())

    def choose(self,run,index=0,decision='accept'):
        item=run.items.get();clip=item.result['clips'][index]
        review.choose(self.owner,run.pk,item.pk,clip['id'],decision,[])
        item.refresh_from_db();return item.result['clips'][index]

    def test_checklist_saved_without_calls_and_changed_audio_resets_it(self):
        entry=self.seed();self.old_audio(entry)
        with patch.object(exp.tts,'synthesize') as api:
            self.mark(entry.current_text,'keep')
            self.assertContains(self.client.get(self.url()),'1 kept')
            self.mark(entry.current_text)
            self.assertContains(self.client.get(self.url()),'1 need regeneration')
            self.assertContains(self.client.get(reverse('community_dictionary:tools',args=[self.dictionary.pk])),'Review homograph audio')
        api.assert_not_called();self.assertFalse(CreditLedgerEntry.objects.exists())
        self.old_audio(entry)
        self.assertEqual(review.rows_for(self.owner,self.dictionary)[0]['decision'],'')

    def test_checklist_renders_forms_and_lemmas_with_and_without_context(self):
        verb = self.seed('courir', 'run')
        word = self.seed('queue', 'tail')
        self.seed('pain', 'bread')
        sentence = self.seed('Il court, la queue levée.', 'He runs with his tail raised.', kind='sentence')
        link = SentenceWord.objects.create(sentence_text=sentence.current_text,
            word_entry=verb, word_text=verb.current_text, surface='court')
        form = sf.publish(link, 'runs', self.owner, {'origin':'synthetic'})
        SentenceWord.objects.create(sentence_text=sentence.current_text,
            word_entry=word, word_text=word.current_text, surface='queue')
        self.old_audio(sentence, form)
        with patch.object(exp.tts, 'synthesize') as api:
            response = self.client.get(self.url())
        self.assertContains(response, 'court')
        self.assertContains(response, 'queue')
        self.assertContains(response, 'pain')
        self.assertContains(response, sentence.word, count=2)
        api.assert_not_called()

    def test_stale_tab_csrf_and_access_controls(self):
        entry=self.seed();audio=self.old_audio(entry);row=review.live_row(self.dictionary,entry.current_text_id)
        data={'action':'keep','part':row['id'],'token':review.fingerprint(row),'previous':''}
        self.assertEqual(self.client.post(self.url(),data).status_code,302)
        self.assertEqual(self.client.post(self.url(),data).status_code,409)
        csrf=Client(enforce_csrf_checks=True);csrf.force_login(self.owner)
        self.assertEqual(csrf.post(self.url(),data).status_code,403)
        self.client.force_login(self.member)
        for url in [self.url(),self.url('current',row['id'],audio.pk)]:self.assertEqual(self.client.get(url).status_code,404)
        self.client.logout();self.assertEqual(self.client.get(self.url()).status_code,302)

    def test_generation_settles_once_and_replacement_requires_explicit_acceptance(self):
        entry=self.seed();old=self.old_audio(entry);run=self.quote([entry])
        self.assertEqual(review.quote(self.owner,self.dictionary,run.pk).pk,run.pk)
        self.assertFalse(CreditLedgerEntry.objects.exists())
        self.assertContains(self.client.get(self.url('run',run.pk)),'Generate replacement previews')
        self.approve(run);self.approve(run);carried,guided=self.finish(run)
        carried.assert_not_called();self.assertEqual(guided.call_count,1)
        self.assertEqual(guided.call_args.kwargs['language'],'fr');self.assertEqual(guided.call_args.kwargs['meaning'],'tail')
        old.refresh_from_db();self.assertEqual(old.status,'accepted')
        self.assertEqual(entry.contributions.filter(kind='audio').count(),1)
        self.assertTrue(run.settled);self.assertEqual(run.charged_usd,Decimal('.001'))
        self.assertEqual(CreditLedgerEntry.objects.count(),2)
        self.assertContains(self.client.get(self.url('run',run.pk)),'New preview')
        clip=self.choose(run);new=Contribution.objects.get(pk=clip['accepted_audio_id'])
        old.refresh_from_db();self.assertEqual(old.status,'superseded');self.assertTrue(path_for(old.file_path).exists())
        self.assertEqual(new.previous_revision_id,old.pk);self.assertEqual(new.shared_from_id,entry.current_text_id)
        self.assertEqual(new.provenance['source_meaning_id'],entry.current_meaning_id)
        self.assertIn(new.pk,dependent_ids([entry.current_meaning_id]))
        self.choose(run);self.assertEqual(entry.contributions.filter(kind='audio').count(),2)
        self.assertEqual(review.rows_for(self.owner,self.dictionary)[0]['decision'],'keep')
        self.assertContains(self.client.get(self.url('run',run.pk)),'Replacement accepted')

    def test_reject_keeps_original_and_allows_fresh_quote(self):
        entry=self.seed();old=self.old_audio(entry);run=self.quote([entry]);self.approve(run);self.finish(run)
        self.choose(run,decision='reject');old.refresh_from_db();self.assertEqual(old.status,'accepted')
        self.assertEqual(entry.contributions.filter(kind='audio').count(),1)
        self.assertEqual(review.rows_for(self.owner,self.dictionary)[0]['decision'],'replace')
        self.assertEqual(review.quote(self.owner,self.dictionary,uuid.uuid4()).items.count(),1)

    def test_human_recordings_protected_at_every_stage(self):
        entry=self.seed();old=self.old_audio(entry,human=True)
        self.assertContains(self.client.get(self.url()),'Human recording present')
        with self.assertRaises(Conflict):self.mark(entry.current_text)
        old.status='superseded';old.save();run=self.quote([entry])
        old.status='accepted';old.save()
        with self.assertRaises(Conflict):self.approve(run)
        old.status='superseded';old.save();self.approve(run);self.finish(run)
        old.status='accepted';old.save()
        with self.assertRaises(Conflict):self.choose(run)
        self.assertEqual(entry.contributions.filter(kind='audio').count(),1)

    def test_two_forms_in_one_sentence_can_be_accepted_independently(self):
        first=self.seed('courir','run');second=self.seed('reposer','put down')
        sentence=self.seed('Il court et repose la tasse.','He runs and puts down the cup.',kind='sentence')
        for word,surface,meaning in [(first,'court','runs'),(second,'repose','puts down')]:
            link=SentenceWord.objects.create(sentence_text=sentence.current_text,word_entry=word,word_text=word.current_text,surface=surface)
            form=sf.publish(link,meaning,self.owner,{'origin':'synthetic'});self.old_audio(sentence,form);self.mark(form)
        run=review.quote(self.owner,self.dictionary,uuid.uuid4());self.assertEqual(run.items.count(),1)
        self.assertEqual(len(run.items.get().snapshot['words']),2);self.approve(run);self.finish(run)
        for index in range(2):
            clip=self.choose(run,index);new=Contribution.objects.get(pk=clip['accepted_audio_id'])
            self.assertTrue(sf.audio_current(new));self.assertIn(new.pk,dependent_ids([sentence.current_text_id]))
        self.assertEqual(sentence.contributions.filter(kind='audio',status='accepted').count(),2)

    def test_preview_ranges_withdrawal_and_separate_published_file(self):
        entry=self.seed(author=self.member);self.old_audio(entry);run=self.quote([entry]);self.approve(run);self.finish(run)
        item=run.items.get();clip=item.result['clips'][0];preview=clip['path'];url=self.url('preview',run.pk,item.pk,clip['id'])
        response=self.client.get(url,HTTP_RANGE='bytes=0-15');self.assertEqual(response.status_code,206);response.close()
        self.choose(run);new=Contribution.objects.get(provenance__homograph_repair_run=str(run.pk))
        with patch.object(port_tasks,'send'),self.captureOnCommitCallbacks(execute=True):withdraw_all(self.member,self.dictionary.pk,0)
        item.refresh_from_db();self.assertTrue(item.invalidated);self.assertEqual(item.snapshot,{'words':[]})
        self.assertFalse(path_for(preview).exists());self.assertTrue(path_for(new.file_path).exists())
        self.assertNotEqual(new.file_path,preview);self.assertNotEqual(self.client.get(url).status_code,200)

    def test_changed_recording_blocks_replacement(self):
        entry=self.seed();self.old_audio(entry);run=self.quote([entry]);self.approve(run);self.finish(run);self.old_audio(entry)
        with self.assertRaises(Conflict):self.choose(run)
        self.assertContains(self.client.get(self.url('run',run.pk)),'Some sources or recordings changed')
        self.assertEqual(entry.contributions.filter(kind='audio').count(),2)

    def test_unknown_cost_failure_is_not_retried_and_does_not_replace(self):
        entry=self.seed();old=self.old_audio(entry);run=self.quote([entry]);self.approve(run)
        def failed(text,**kw):
            kw['before_request']();kw['report']['uncertain_cost']=True;raise TimeoutError
        _carried,guided=self.finish(run,guidance_fn=failed)
        self.assertEqual(guided.call_count,1);self.assertEqual(run.charged_usd,run.allowance_usd)
        self.assertEqual(run.items.get().result['clips'][0]['status'],'failed')
        old.refresh_from_db();self.assertEqual(old.status,'accepted')
        self.assertContains(self.client.get(self.url('run',run.pk)),'No usable recording')

    def test_expired_quote_insufficient_funds_and_concurrent_jobs(self):
        entry=self.seed();run=self.quote([entry]);run.expires_at=timezone.now()-timedelta(seconds=1);run.save()
        with self.assertRaises(Conflict):self.approve(run)
        run.expires_at=timezone.now()+timedelta(hours=1);run.save();CreditAccount.objects.filter(user=self.owner).update(balance_usd=0)
        with self.assertRaises(Conflict):self.approve(run)
        CreditAccount.objects.filter(user=self.owner).update(balance_usd=100)
        second=review.quote(self.owner,self.dictionary,uuid.uuid4());self.approve(run)
        with self.assertRaises(Conflict):self.approve(second)
        self.finish(run);self.approve(second)

    def test_generic_publication_is_blocked(self):
        run=self.quote();self.approve(run);self.finish(run);item=run.items.get()
        with self.assertRaises(Conflict):porting.save_item(self.owner,item.pk,{})
        self.assertEqual(self.client.get(reverse('community_dictionary:port-review',args=[self.dictionary.pk,run.pk,item.pk])).status_code,302)

    def test_real_adapter_uses_guidance_and_exact_word(self):
        run=self.quote();self.approve(run)
        with provider([carrier_wave()]) as (coach,speech,_),patch.object(port_tasks,'send'),self.captureOnCommitCallbacks(execute=True):port_tasks.process_item(run.items.get().pk)
        run.refresh_from_db();self.assertTrue(run.settled);self.assertEqual(coach.call_count,1)
        self.assertEqual(speech.call_args.kwargs['input'],'queue');self.assertTrue(run.items.get().result['clips'][0]['report']['guidance'])

    def test_cancelled_interrupted_call_accounted_once_without_replay(self):
        run=self.quote();self.approve(run);item=run.items.get();clip=item.result['clips'][0]
        clip['status']='running';item.status='running';item.started_at=timezone.now()-timedelta(minutes=16)
        item.usage={'homograph_claim':{'id':clip['id'],'allowance':clip['allowance']}};item.save()
        with patch.object(port_tasks,'send'),self.captureOnCommitCallbacks(execute=True):
            porting.cancel(self.owner,run.pk);exp.resume(self.owner,run.pk)
        run.refresh_from_db();self.assertTrue(run.settled);self.assertEqual(run.charged_usd,Decimal(clip['allowance']))
        with patch.object(exp.tts,'synthesize') as calls:port_tasks.process_item(item.pk)
        calls.assert_not_called()

    def test_review_supports_guidance_languages_without_carrier_templates(self):
        self.dictionary.language='Spanish';self.dictionary.save()
        run=self.quote([self.seed('pie','foot')]);self.approve(run)
        carried,guided=self.finish(run)
        self.assertTrue(run.settled);carried.assert_not_called()
        self.assertEqual(guided.call_args.kwargs['language'],'es')

    def test_french_interface_and_legacy_human_form_protection(self):
        self.client.cookies['community_ui_language']='fr'
        self.assertContains(self.client.get(self.url()),'homographes')
        word=self.seed('courir','run');sentence=self.seed('Il court.','He runs.',kind='sentence')
        link=SentenceWord.objects.create(sentence_text=sentence.current_text,word_entry=word,word_text=word.current_text,surface='court')
        form=sf.publish(link,'runs',self.owner,{'origin':'synthetic'})
        audio=self.old_audio(sentence,form,human=True);audio.provenance={};audio.save()
        with self.assertRaises(Conflict):self.mark(form)
