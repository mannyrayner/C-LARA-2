"""Offline paired experiment, payment, privacy, recovery and rating contracts."""
import csv
import io
import uuid
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase, SimpleTestCase, Client, override_settings
from django.urls import reverse
from django.utils import timezone
from community_dictionary import homograph_experiments as exp, carrier, porting, port_tasks, sentence_forms as sf
from community_dictionary.models import Contribution, Entry, PortRun, SentenceWord
from community_dictionary.services import accept, Conflict
from community_dictionary.storage import path_for, write_upload
from community_dictionary.participation import withdraw_all
from projects.models import CreditAccount, CreditLedgerEntry
from . import test_workflow as workflow
from .test_mwe_audio import carrier_wave
from .test_tts_guidance import provider


class CarrierExperimentTests(SimpleTestCase):
    def test_single_word_is_only_available_through_explicit_experiment(self):
        for word in ['court', 'repose', 'queue']:
            self.assertTrue(carrier.homograph_eligible(word, 'French'))
            self.assertFalse(carrier.eligible(word, 'French'))
        for word, language in [('queue', 'English'), ('cat', 'Spanish'), ('court.', 'French'), ('fromage', 'French')]:
            self.assertFalse(carrier.homograph_eligible(word, language))
        full, report, kept = carrier_wave(), {}, []
        args = dict(language='fr', model='gpt-4o-mini-tts', voice='marin', api_key='test', report=report)
        with self.assertRaises(ValueError):
            carrier.synthesize('queue', **args)
        with provider([full]) as (_, speech, _):
            prepared, duration = carrier.synthesize('queue', **args, homograph_experiment=True,
                keep_full=kept.append)
        self.assertEqual(speech.call_args.kwargs['input'], 'On commence. queue. C’est fini.')
        self.assertEqual(report['strategy'], 'homograph_carrier_experiment')
        self.assertEqual(kept[0][0], full)
        self.assertLess(len(prepared[0]), len(full))


@override_settings(OPENAI_API_KEY='fixture-only', CREDITS_ENABLED=True,
    COMMUNITY_DICTIONARY_PORT_WINDOW=2, PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class ExperimentTests(TestCase):
    def setUp(self):
        workflow.WorkflowTests.setUp(self)
        self.dictionary.language = 'French'
        self.dictionary.explanation_language = 'English'
        self.dictionary.save()
        CreditAccount.objects.create(user=self.owner, balance_usd=100)
        self.client.force_login(self.owner)

    def url(self, name, *args):
        return reverse('community_dictionary:homographs-'+name, args=[self.dictionary.pk, *args])

    def seed(self, word='queue', meaning='tail', kind='word', author=None):
        entry = Entry.objects.create(dictionary=self.dictionary, created_by=author or self.owner, entry_type=kind)
        for field, value in [('word', word), ('meaning', meaning)]:
            part = Contribution.objects.create(entry=entry, author=author or self.owner, kind='text',
                text_field=field, **{field:value})
            accept(part, self.owner)
        entry.refresh_from_db()
        return entry

    def quote(self, entries=None, repeats=2):
        entries = entries or [self.seed()]
        return exp.quote(self.owner, self.dictionary, uuid.uuid4(),
            [e.current_text_id for e in entries], repeats)

    def approve(self, run):
        with patch.object(port_tasks, 'send'), self.captureOnCommitCallbacks(execute=True):
            porting.approve(self.owner, run.pk)
        run.refresh_from_db()

    @staticmethod
    def synthesis(text, **kw):
        kw['before_request']()
        kw['report'].update(speech_cost_usd='.001', guidance_cost_usd='0', attempts=[{'outcome':'ready'}])
        data = (carrier_wave(), 'audio/wav', '.wav')
        if kw.get('keep_full'):
            kw['keep_full'](data)
        return data, 3.2

    def finish(self, run, carrier_fn=None, guidance_fn=None):
        with patch.object(exp.carrier, 'synthesize', side_effect=carrier_fn or self.synthesis) as carried, \
             patch.object(exp.tts, 'synthesize', side_effect=guidance_fn or self.synthesis) as guided, \
             patch.object(port_tasks, 'send'), self.captureOnCommitCallbacks(execute=True):
            for _ in range(125):
                port_tasks.dispatch(str(run.pk))
                items = list(run.items.filter(status='queued'))
                if not items:
                    break
                for item in items:
                    port_tasks.process_item(item.pk)
        run.refresh_from_db()
        return carried, guided

    def ratings(self, run, value='acceptable'):
        run.refresh_from_db()
        data = {'revision':str(run.options['ratings_revision'])}
        for item in run.items.all():
            for clip in item.result.get('clips', []):
                if clip['status']=='ready':
                    data['rating_'+clip['id']] = value
                    data['note_'+clip['id']] = 'Natural pronunciation'
        return data

    def test_quote_is_idempotent_and_does_not_spend_or_call_provider(self):
        entry = self.seed()
        token = uuid.uuid4()
        with patch.object(exp.tts, 'synthesize') as api:
            run = exp.quote(self.owner, self.dictionary, token, [entry.current_text_id], 2)
            again = exp.quote(self.owner, self.dictionary, token, [entry.current_text_id], 2)
        self.assertEqual(run.pk, again.pk)
        self.assertEqual(run.items.count(), 1)
        self.assertEqual(len(run.items.get().result['clips']), 4)
        self.assertFalse(CreditLedgerEntry.objects.exists())
        api.assert_not_called()
        self.assertGreater(run.allowance_usd, run.estimated_usd)
        self.assertContains(self.client.get(self.url('run', run.pk)), 'Generate comparison recordings')
        self.assertContains(self.client.get(self.url('start')), 'queue')
        with self.assertRaises(Conflict):
            exp.quote(self.owner, self.dictionary, uuid.uuid4(), [], 2)
        with self.assertRaises(Conflict):
            exp.quote(self.owner, self.dictionary, uuid.uuid4(), [entry.current_text_id], 4)

    def test_generation_does_not_publish_or_replace_audio_and_settles_once(self):
        entry = self.seed()
        original = Contribution.objects.create(entry=entry, author=self.owner, kind='audio', status='accepted',
            **write_upload((carrier_wave(),'audio/wav','.wav'), self.dictionary.pk, []))
        before = Contribution.objects.count()
        run = self.quote([entry]); self.approve(run); self.approve(run)
        carried, guided = self.finish(run)
        self.assertEqual((carried.call_count, guided.call_count), (2,2))
        self.assertTrue(carried.call_args.kwargs['homograph_experiment'])
        self.assertEqual(guided.call_args.kwargs['meaning'], 'tail')
        self.assertEqual(guided.call_args.kwargs['language'], 'fr')
        self.assertEqual(guided.call_args.kwargs['speech_kind'], 'entry')
        self.assertEqual(run.status, 'complete'); self.assertTrue(run.settled)
        self.assertEqual(run.charged_usd, Decimal('.004'))
        self.assertEqual(Contribution.objects.count(), before)
        original.refresh_from_db(); self.assertEqual(original.status,'accepted')
        self.assertTrue(path_for(original.file_path).is_file())
        self.assertEqual(CreditAccount.objects.get(user=self.owner).balance_usd, Decimal('99.996'))
        self.assertEqual(CreditLedgerEntry.objects.count(), 2)
        again = self.finish(run)
        self.assertEqual(sum(x.call_count for x in again), 0)
        self.assertEqual(CreditLedgerEntry.objects.count(), 2)

    def test_insufficient_credit_expiry_and_changed_source_block_approval(self):
        run = self.quote()
        CreditAccount.objects.filter(user=self.owner).update(balance_usd=0)
        with self.assertRaises(Conflict): self.approve(run)
        CreditAccount.objects.filter(user=self.owner).update(balance_usd=100)
        PortRun.objects.filter(pk=run.pk).update(expires_at=timezone.now()-timedelta(seconds=1))
        with self.assertRaises(Conflict): self.approve(run)
        other = self.quote()
        Contribution.objects.filter(pk=other.items.get().snapshot['words'][0]['id']).update(word='chat')
        with self.assertRaises(Conflict): self.approve(other)
        self.assertFalse(CreditLedgerEntry.objects.exists())

    def test_owner_private_media_blind_ratings_reveal_export_and_stale_tab(self):
        run = self.quote(); self.approve(run); self.finish(run)
        item = run.items.get(); clips = item.result['clips']
        clip = next(c for c in clips if c['method']=='carrier')
        url = self.url('media',run.pk,item.pk,clip['id'])
        response = self.client.get(url); self.assertEqual(response.status_code, 200); response.close()
        self.assertEqual(self.client.get(url+'?full=1').status_code,404)
        response = self.client.get(self.url('run',run.pk))
        self.assertNotContains(response, 'Current pronunciation guidance')
        self.assertNotContains(response, 'Carrier phrase with extraction')
        self.assertNotContains(response, clip['full_path'])
        self.assertEqual(self.client.get(self.url('export',run.pk)).status_code,409)
        old = self.ratings(run)
        response = self.client.post(self.url('run',run.pk), {**old,'action':'save'})
        self.assertEqual(response.status_code,302)
        self.assertEqual(self.client.post(self.url('run',run.pk),{**old,'action':'save'}).status_code,409)
        self.assertEqual(self.client.post(self.url('run',run.pk),{**self.ratings(run),'action':'reveal'}).status_code,302)
        self.assertContains(self.client.get(self.url('run',run.pk)), 'Carrier phrase with extraction')
        response = self.client.get(url+'?full=1'); self.assertEqual(response.status_code,200); response.close()
        csv_result = self.client.get(self.url('export',run.pk))
        rows = list(csv.DictReader(io.StringIO(csv_result.content.decode('utf-8-sig'))))
        self.assertEqual(len(rows),4); self.assertEqual({r['method'] for r in rows}, {'guidance','carrier'})
        changed = self.ratings(run,'minor'); changed['note_'+clip['id']] = '=1+2'
        self.client.post(self.url('run',run.pk),{**changed,'action':'save'})
        result = self.client.get(self.url('export',run.pk)).content.decode('utf-8-sig')
        self.assertIn("'=1+2",result); self.assertIn('True',result)
        for user in [self.member,self.outsider]:
            self.client.force_login(user)
            self.assertEqual(self.client.get(url).status_code,404)
            self.assertEqual(self.client.get(self.url('run',run.pk)).status_code,404)
        self.client.logout(); self.assertEqual(self.client.get(url).status_code,302)

    def test_reveal_requires_all_ratings_and_csrf(self):
        run=self.quote(); self.approve(run); self.finish(run)
        self.assertEqual(self.client.post(self.url('run',run.pk), {'revision':'0','action':'reveal'}).status_code,409)
        client = Client(enforce_csrf_checks=True); client.force_login(self.owner)
        self.assertEqual(client.post(self.url('run',run.pk),{'action':'save'}).status_code,403)

    def test_source_withdrawal_removes_completed_files_and_private_results(self):
        entry = self.seed(author=self.member)
        run=self.quote([entry]); self.approve(run); self.finish(run)
        item=run.items.get(); clip=item.result['clips'][0]
        files = [c[k] for c in item.result['clips'] for k in ('path','full_path') if k in c]
        self.assertTrue(all(path_for(p).exists() for p in files))
        self.dictionary.refresh_from_db()
        with patch.object(port_tasks,'send'), self.captureOnCommitCallbacks(execute=True):
            withdraw_all(self.member,self.dictionary.pk,self.dictionary.membership_revision)
        item.refresh_from_db()
        self.assertEqual(item.result,{})
        self.assertEqual(item.snapshot, {'words':[]})
        self.assertFalse(any(path_for(p).exists() for p in files))
        self.assertEqual(self.client.get(self.url('media',run.pk,item.pk,clip['id'])).status_code,409)
        self.assertNotContains(self.client.get(self.url('run',run.pk)), 'tail')

    def test_extraction_failure_is_not_silently_replaced_and_remains_in_summary(self):
        def fails(text, **kw):
            self.synthesis(text,**kw)
            raise carrier.ExtractionFailed('private debug')
        run=self.quote(repeats=1);self.approve(run)
        carried,guided=self.finish(run,carrier_fn=fails)
        self.assertEqual((carried.call_count,guided.call_count),(1,1))
        clips=run.items.get().result['clips']
        failed=next(c for c in clips if c['status']=='failed')
        self.assertNotIn('path',failed);self.assertIn('full_path',failed)
        self.assertEqual(failed['failure'],'extraction')
        exp.save_ratings(run.pk,self.ratings(run),reveal=True)
        self.assertEqual(sum(s['failed'] for s in exp.table(run)[1]),1)

    def test_network_failure_unknown_cost_is_not_retried(self):
        def fails(text, **kw):
            kw['before_request']();kw['report']['uncertain_cost']=True
            raise TimeoutError('not exposed')
        run=self.quote(repeats=1);self.approve(run)
        calls=self.finish(run,guidance_fn=fails)
        self.assertEqual(calls[1].call_count,1)
        item=run.items.get();self.assertTrue(item.uncertain_cost)
        expected=sum(Decimal(c['cost']) for c in item.result['clips'])
        self.assertEqual(run.charged_usd,porting.money(expected))
        self.assertNotContains(self.client.get(self.url('run',run.pk)),'not exposed')

    def test_duplicate_worker_and_interrupted_recovery_do_not_repeat_claim(self):
        run=self.quote(repeats=1);self.approve(run)
        item=run.items.get();clip=item.result['clips'][0];clip['status']='running'
        item.status='running';item.started_at=timezone.now()-timedelta(minutes=16)
        item.save()
        with patch.object(exp.tts,'synthesize') as call:
            exp.process(item.pk)
        call.assert_not_called()
        with patch.object(port_tasks,'send'),self.captureOnCommitCallbacks(execute=True):
            exp.resume(self.owner,run.pk)
        item.refresh_from_db();self.assertEqual(item.result['clips'][0]['status'],'failed')
        calls=self.finish(run)
        self.assertEqual(sum(x.call_count for x in calls),1)
        self.assertEqual(run.status,'complete')

    def test_sentence_forms_are_separate_candidates_and_revisions_are_guarded(self):
        word=self.seed('courir','run')
        sentence=self.seed('Le chien court.','The dog is running.',kind='sentence')
        link=SentenceWord.objects.create(sentence_text=sentence.current_text,word_entry=word,
            word_text=word.current_text,surface='court')
        form=sf.publish(link,'is running',self.owner,{'origin':'synthetic'})
        candidates=exp.candidates(self.dictionary)
        self.assertEqual([c['word'] for c in candidates],['court'])
        run=exp.quote(self.owner,self.dictionary,uuid.uuid4(),[form.pk],1)
        self.approve(run);self.finish(run)
        self.assertEqual(run.items.get().snapshot['words'][0]['context'],'Le chien court.')
        Contribution.objects.filter(pk=form.pk).update(meaning='runs')
        self.assertEqual(exp.table(run)[0],[])

    def test_real_adapters_get_exact_word_language_and_separate_methods(self):
        run=self.quote(repeats=1); self.approve(run)
        with provider([carrier_wave(),carrier_wave()]) as (coach,speech,_), \
             patch.object(port_tasks,'send'),self.captureOnCommitCallbacks(execute=True):
            for _ in range(3):
                port_tasks.dispatch(str(run.pk))
                for item in run.items.filter(status='queued'):
                    port_tasks.process_item(item.pk)
        run.refresh_from_db()
        self.assertEqual(run.status,'complete')
        self.assertEqual(coach.call_count,1)
        self.assertEqual({c.kwargs['input'] for c in speech.call_args_list},
                         {'queue','On commence. queue. C’est fini.'})
        reports={c['method']:c['report'] for c in run.items.get().result['clips']}
        self.assertTrue(reports['guidance']['guidance'])
        self.assertEqual(reports['guidance']['english_homographs'],['queue'])
        self.assertEqual(reports['carrier']['strategy'],'homograph_carrier_experiment')

    def test_cancel_in_flight_never_saves_audio_but_accounts_for_completed_call(self):
        run=self.quote(repeats=1);self.approve(run)
        def cancel_mid_call(text, **kw):
            result=self.synthesis(text,**kw)
            porting.cancel(self.owner,run.pk)
            return result
        self.finish(run,carrier_fn=cancel_mid_call,guidance_fn=cancel_mid_call)
        run.refresh_from_db();self.assertEqual(run.status,'cancelled')
        self.assertTrue(run.settled);self.assertEqual(run.charged_usd,Decimal('.001'))
        self.assertEqual(run.items.get().result,{})
        self.assertEqual(list(path_for(str(self.dictionary.pk)).glob('*.wav')),[])

    def test_cancelled_lost_worker_can_settle_without_replaying_request(self):
        run=self.quote(repeats=1);self.approve(run)
        item=run.items.get();clip=item.result['clips'][0];clip['status']='running'
        item.status='running';item.started_at=timezone.now()-timedelta(minutes=16)
        item.usage={'homograph_claim':{'id':clip['id'],'allowance':clip['allowance']}}
        item.save()
        with patch.object(port_tasks,'send'),self.captureOnCommitCallbacks(execute=True):
            porting.cancel(self.owner,run.pk)
            exp.resume(self.owner,run.pk)
        run.refresh_from_db();item.refresh_from_db()
        self.assertTrue(run.settled);self.assertEqual(run.charged_usd,Decimal(clip['allowance']))
        self.assertEqual(item.result,{});self.assertEqual(item.status,'discarded')
        with patch.object(exp.tts,'synthesize') as calls:
            exp.process(item.pk)
        calls.assert_not_called()

    def test_generic_language_port_review_cannot_publish_experimental_audio(self):
        run=self.quote(repeats=1);self.approve(run);self.finish(run)
        with self.assertRaises(Conflict):
            porting.save_item(self.owner,run.items.get().pk,{'word':'queue','meaning':'tail','category':''})
        url=reverse('community_dictionary:port-review',args=[self.dictionary.pk,run.pk,run.items.get().pk])
        response=self.client.get(url)
        self.assertRedirects(response,self.url('run',run.pk))
