"""Offline carrier extraction, guarded batch replacement and paired evaluation."""
from array import array
from decimal import Decimal
import io
import math
import sys
import uuid
import wave
from unittest.mock import Mock, patch

from django.test import SimpleTestCase, TestCase, Client, override_settings
from django.urls import reverse
from django.utils import timezone

from community_dictionary import carrier, carrier_audio, evaluation as ev, mwe_audio, porting
from community_dictionary import port_tasks, port_vocabulary_tasks as jobs
from community_dictionary.models import (Contribution, Entry, EvaluationSet, LanguageCompetence,
    Participation, PortRun, WithdrawalHold)
from community_dictionary.services import Conflict, accept
from community_dictionary.lexicon import recordings
from community_dictionary.storage import path_for, write_upload
from projects.models import CreditAccount, CreditLedgerEntry
from .test_tts_guidance import provider, quiet
from . import test_workflow as workflow
from .test_porting import speech


def carrier_wave(sections=(.5, .6, 1., .6, .5)):
    rate = 24000
    samples = array('h')
    for part, seconds in enumerate(sections):
        samples.extend(int(2000*math.sin(2*math.pi*440*i/rate)) if part%2==0 else 0
                       for i in range(round(seconds*rate)))
    if sys.byteorder != 'little': samples.byteswap()
    data=io.BytesIO()
    with wave.open(data, 'wb') as out:
        out.setparams((1, 2, rate, 0, 'NONE', 'not compressed')); out.writeframes(samples.tobytes())
    return data.getvalue()


class CarrierTests(SimpleTestCase):
    def call(self, report=None, **extra):
        return carrier.synthesize('sträcka ut sig', language='sv', model='gpt-4o-mini-tts',
            voice='marin', api_key='fixture-only', report=report if report is not None else {}, **extra)

    def test_selection_and_frozen_carriers(self):
        for text, lang in [('sträcka ut sig','Swedish'), ('avoir envie de','French'), ('se dresser','fr')]:
            self.assertTrue(carrier.eligible(text,lang))
        for text, lang in [('chat','fr'), ('sträcka ut sig','de'), ('s’habiller','fr'), ('a ; b','fr'), ('A cat.','sv')]:
            self.assertFalse(carrier.eligible(text,lang))
        self.assertEqual(carrier.request('se dresser','fr')[0], 'On commence. se dresser. C’est fini.')
        self.assertEqual(carrier.request('ha på sig','sv')[0], 'Vi börjar. ha på sig. Vi avslutar.')

    def test_exact_pcm_cut_with_padding_and_no_guidance_call(self):
        full = carrier_wave()
        report = {}; gate = Mock()
        with provider([full]) as (coach, calls, factory):
            prepared, duration = self.call(report, before_request=gate)
        coach.assert_not_called(); self.assertEqual(calls.call_count,1); gate.assert_called_once()
        self.assertEqual(calls.call_args.kwargs['input'], 'Vi börjar. sträcka ut sig. Vi avslutar.')
        self.assertEqual(factory.call_args.kwargs['max_retries'],0)
        measure=report['attempts'][0]['extraction']; cut=measure['cut']
        expected=carrier_audio.segment(carrier_audio.load(full),cut['start'],cut['end'],200)
        self.assertEqual(prepared[0],expected)
        self.assertAlmostEqual(duration,1.64,places=2)
        self.assertGreater(Decimal(report['speech_cost_usd']),0)

    def test_five_attempts_and_no_unbounded_retry(self):
        with provider([carrier_wave((1.,))]*4+[carrier_wave()]) as (_, calls, _):
            report={};self.call(report)
        self.assertEqual(calls.call_count,5)
        self.assertEqual(len(report['attempts']),5)
        with provider([carrier_wave((1.,))]*5) as (_, calls, _):
            report={}
            with self.assertRaises(carrier.ExtractionFailed):self.call(report)
        self.assertEqual(calls.call_count,5)
        self.assertEqual(report['failure_code'],'extraction')
        self.assertFalse(report['uncertain_cost'])

    def test_silence_retries_but_network_errors_do_not(self):
        with provider([quiet(), carrier_wave()]) as (_, calls, _):
            self.call()
        self.assertEqual(calls.call_count,2)
        for output in [TimeoutError('private message'), b'not wav']:
            with provider([output]) as (_, calls, _):
                report={}
                with self.assertRaises(Exception):self.call(report)
                self.assertEqual(calls.call_count,1)
                self.assertTrue(report['uncertain_cost'])

    def test_ambiguous_extra_gap_and_short_carriers_rejected(self):
        for data in [carrier_wave((.5,.6,.5,.6,.5,.6,.5)),carrier_wave((.1,.6,1.,.6,.5))]:
            self.assertEqual(carrier_audio.measure(carrier_audio.load(data),carrier_audio.DEFAULT)['status'],'ambiguous')


@override_settings(OPENAI_API_KEY='fixture-only', CREDITS_ENABLED=True,
    COMMUNITY_DICTIONARY_PORT_WINDOW=2, PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class BatchTests(TestCase):
    setUp = workflow.WorkflowTests.setUp

    def seed(self, word='sträcka ut sig', *, human=False, kind='word', author=None):
        author = author or self.owner
        entry=Entry.objects.create(dictionary=self.dictionary, created_by=author, entry_type=kind)
        text=Contribution.objects.create(entry=entry, author=author, kind='text', text_field='word', word=word)
        accept(text,self.owner);entry.refresh_from_db()
        audio=Contribution.objects.create(entry=entry,author=author,kind='audio',shared_from=text,
            provenance={} if human else {'origin':'synthetic','source_text':word,'language':'Swedish','voice':'marin'},
            **write_upload(speech()[0],self.dictionary.pk,[]))
        accept(audio,self.owner)
        return entry,audio

    def quote(self):
        return mwe_audio.quote(self.owner,self.dictionary,uuid.uuid4())

    def approve(self, run):
        CreditAccount.objects.update_or_create(user=self.owner, defaults={'balance_usd':Decimal('5')})
        with patch.object(jobs,'send_speech'), self.captureOnCommitCallbacks(execute=True):
            porting.approve(self.owner,run.pk)
        run.refresh_from_db()
        return run

    def finish(self, run, effect=None):
        def generated(*args,**kw):
            kw['before_request']()
            kw['report'].update(speech_cost_usd='0.002',guidance_cost_usd='0',attempts=[{'outcome':'candidate'}])
            return speech()
        with patch.object(carrier,'synthesize',side_effect=effect or generated) as call, patch.object(jobs,'send_speech'):
            for pk in run.speech.values_list('pk',flat=True):jobs.speak(pk)
        run.refresh_from_db()
        return call

    def test_free_quote_protected_scope_approval_and_idempotency(self):
        entry,old=self.seed();self.seed('katt');self.seed('ha på sig',human=True);self.seed('En katt sover',kind='sentence')
        run=self.quote()
        self.assertEqual(run.items.count(),1);self.assertEqual(run.items.get().source_entry,entry)
        self.assertFalse(CreditLedgerEntry.objects.exists())
        self.assertEqual(mwe_audio.quote(self.owner,self.dictionary,run.pk).pk,run.pk)
        self.approve(run)
        reservations=CreditLedgerEntry.objects.count()
        porting.approve(self.owner,run.pk)
        self.assertEqual(CreditLedgerEntry.objects.count(),reservations)
        call=self.finish(run)
        self.assertEqual(call.call_count,1)
        self.assertEqual(run.status,'complete');self.assertTrue(run.settled)
        self.assertEqual(run.charged_usd,Decimal('.002'))
        self.assertEqual(CreditAccount.objects.get(user=self.owner).balance_usd,Decimal('4.998'))
        jobs.speak(run.speech.get().pk)
        old.refresh_from_db();self.assertEqual(old.status,'superseded');self.assertTrue(path_for(old.file_path).exists())
        new=recordings(entry,self.dictionary)[0]
        self.assertEqual(new.provenance['instructions_version'],carrier.VERSION)
        self.assertEqual(new.previous_revision,old)
        self.assertEqual(new.shared_from_id,entry.current_text_id)
        self.assertFalse(self.quote().items.exists())

    def test_failure_keeps_old_audio_and_explicit_retry_excludes_success(self):
        entry,old=self.seed();run=self.approve(self.quote())
        def fail(*args,**kw):
            kw['report'].update(speech_cost_usd='.003',guidance_cost_usd='0')
            raise carrier.ExtractionFailed()
        self.finish(run,fail)
        old.refresh_from_db();self.assertEqual(old.status,'accepted')
        self.assertEqual(run.speech.get().status,'failed');self.assertTrue(run.settled)
        self.assertEqual(run.charged_usd,Decimal('.003'))
        self.assertEqual(self.quote().items.count(),1)

    def test_changed_text_or_recording_aborts_before_provider(self):
        entry,old=self.seed();run=self.approve(self.quote())
        Contribution.objects.filter(pk=old.pk).update(status='withdrawn')
        call=self.finish(run)
        call.assert_not_called();self.assertEqual(run.speech.get().status,'discarded')
        self.assertEqual(run.charged_usd,0)

    def test_change_during_provider_discards_output_but_accounts_cost(self):
        entry,old=self.seed();run=self.approve(self.quote())
        def change(*args,**kw):
            kw['report'].update(speech_cost_usd='.002')
            Contribution.objects.filter(pk=old.pk).update(status='withdrawn')
            return speech()
        self.finish(run,change)
        self.assertEqual(run.speech.get().status,'discarded')
        self.assertEqual(entry.contributions.filter(kind='audio').count(),1)
        self.assertEqual(run.charged_usd,Decimal('.002'))

    def test_restore_preserves_both_files_and_is_repeatable(self):
        entry,old=self.seed();run=self.approve(self.quote());self.finish(run)
        new=recordings(entry,self.dictionary)[0]
        self.assertEqual(mwe_audio.restore(self.owner,run),(1,0))
        self.assertEqual(mwe_audio.restore(self.owner,run),(0,0))
        old.refresh_from_db();new.refresh_from_db()
        self.assertEqual(old.status,'accepted');self.assertEqual(new.status,'superseded')
        self.assertTrue(path_for(new.file_path).exists())

    def test_restore_never_resurrects_withdrawn_old_audio(self):
        entry,old=self.seed();run=self.approve(self.quote());self.finish(run)
        Contribution.objects.filter(pk=old.pk).update(status='withdrawn')
        self.assertEqual(mwe_audio.restore(self.owner,run),(0,1))
        old.refresh_from_db();self.assertEqual(old.status,'withdrawn')

    def test_only_owner_csrf_and_no_photo_permission_required(self):
        self.seed();self.dictionary.photo_ai_enabled=False;self.dictionary.save()
        url=reverse('community_dictionary:mwe-audio',args=[self.dictionary.pk])
        self.assertEqual(self.client.get(url).status_code,404)
        self.client.force_login(self.owner)
        self.assertContains(self.client.get(url),'Show estimate')
        run=self.quote();self.approve(run);self.finish(run)
        self.assertContains(self.client.get(reverse('community_dictionary:mwe-audio-run',args=[self.dictionary.pk,run.pk])), 'Replacement saved')
        csrf=Client(enforce_csrf_checks=True);csrf.force_login(self.owner)
        self.assertEqual(csrf.post(url,{'token':uuid.uuid4()}).status_code,403)

    def test_insufficient_credit_and_tts_disable(self):
        self.seed();run=self.quote()
        with self.assertRaises(Conflict):porting.approve(self.owner,run.pk)
        self.dictionary.tts_enabled=False;self.dictionary.save()
        with self.assertRaises(Conflict):self.quote()

    def test_cancel_before_work_and_duplicate_job_approval(self):
        entry,old=self.seed();a=self.quote();b=self.quote();self.approve(a)
        with self.assertRaises(Conflict):porting.approve(self.owner,b.pk)
        porting.cancel(self.owner,a.pk)
        self.finish(a).assert_not_called()
        self.assertEqual(a.status,'cancelled');self.assertTrue(a.settled)
        old.refresh_from_db();self.assertEqual(old.status,'accepted')

    def test_audio_only_baseline_and_same_entry_followup(self):
        entry,old=self.seed();self.seed('katt')
        data={'token':uuid.uuid4(),'name':'Before','scope':'word_audio','sampling':'all',
              'size':30,'allow_visitors':False,'mwe_only':True}
        baseline=ev.create_set(self.owner,self.dictionary,data)
        self.assertEqual(baseline.items.count(),1)
        self.assertEqual(set(baseline.units.values_list('dimension',flat=True)),{'word_audio'})
        self.assertEqual(baseline.items.get().snapshot['entry']['audio']['id'],old.pk)
        baseline.closed_at=timezone.now();baseline.save()
        run=self.approve(self.quote());self.finish(run)
        self.assertIn(baseline.items.get().pk,ev.available_items(list(baseline.items.all()),self.dictionary))
        follow=ev.create_set(self.owner,self.dictionary,{**data,'token':uuid.uuid4(),'based_on':baseline})
        self.assertEqual(follow.based_on,baseline)
        self.assertEqual(list(follow.items.values_list('entry_id',flat=True)),[entry.pk])
        self.assertNotEqual(follow.items.get().snapshot['entry']['audio']['id'],old.pk)
        self.assertEqual(baseline.items.get().snapshot['entry']['audio']['id'],old.pk)
        skills={'target':{'reading':3,'listening':3},'explanation':{'reading':3,'listening':3}}
        self.assertEqual(ev.eligible_dimensions(skills,'word_audio'),['word_audio'])

    def test_repeat_requires_closed_set_and_retains_membership_checks(self):
        self.seed()
        baseline=ev.create_set(self.owner,self.dictionary,{'token':uuid.uuid4(),'name':'Before',
            'scope':'words','sampling':'all','size':30,'allow_visitors':False})
        url=reverse('community_dictionary:evaluation-repeat-audio',args=[self.dictionary.pk,baseline.pk])
        self.assertEqual(self.client.post(url,{'token':uuid.uuid4()}).status_code,404)
        self.client.force_login(self.owner)
        self.assertEqual(self.client.post(url,{'token':uuid.uuid4()}).status_code,409)
        baseline.closed_at=timezone.now();baseline.save()
        token=uuid.uuid4()
        for _ in range(2):self.assertEqual(self.client.post(url,{'token':token}).status_code,302)
        self.assertEqual(EvaluationSet.objects.filter(based_on=baseline).count(),1)

    def test_owner_http_estimate_approve_restore_and_audio_csv(self):
        import csv
        self.seed();self.client.force_login(self.owner)
        start=reverse('community_dictionary:mwe-audio',args=[self.dictionary.pk])
        response=self.client.post(start,{'token':uuid.uuid4()})
        run=PortRun.objects.latest('created_at')
        self.assertRedirects(response,reverse('community_dictionary:mwe-audio-run',args=[self.dictionary.pk,run.pk]))
        self.assertContains(self.client.get(response.url),'Insufficient C-LARA credit')
        CreditAccount.objects.update_or_create(user=self.owner,defaults={'balance_usd':5})
        action=reverse('community_dictionary:port-action',args=[self.dictionary.pk,run.pk])
        self.assertEqual(self.client.post(action,{'action':'approve'}).status_code,400)
        with patch.object(jobs,'send_speech'),self.captureOnCommitCallbacks(execute=True):
            self.assertEqual(self.client.post(action,{'action':'approve','approve':'on'}).status_code,302)
        self.finish(run)
        address=reverse('community_dictionary:mwe-audio-run',args=[self.dictionary.pk,run.pk])
        self.assertContains(self.client.get(address),'Replacement saved')
        data={'token':uuid.uuid4(),'name':'After','scope':'word_audio','sampling':'all','size':30,'allow_visitors':False}
        batch=ev.create_set(self.owner,self.dictionary,data);batch.closed_at=timezone.now();batch.save()
        output=self.client.get(reverse('community_dictionary:evaluation-export',args=[self.dictionary.pk,batch.pk]))
        rows=list(csv.DictReader(io.StringIO(output.content.decode())))
        self.assertEqual(rows[0]['scope'],'word_audio')
        self.assertTrue(rows[0]['audio_contribution_id'])
        self.assertEqual(self.client.post(address,{'action':'restore'}).status_code,302)
        self.assertContains(self.client.get(address),'Earlier audio restored')

    def test_member_withdrawal_removes_replacement_and_blocks_restore(self):
        from community_dictionary.participation import withdraw_all
        entry,old=self.seed(author=self.member);run=self.approve(self.quote());self.finish(run)
        new=recordings(entry,self.dictionary)[0]
        with patch.object(jobs,'send_speech'),self.captureOnCommitCallbacks(execute=True):
            withdraw_all(self.member,self.dictionary.pk,0)
        new.refresh_from_db()
        self.assertTrue(new.entry.dictionary.personal)
        self.assertFalse(Contribution.objects.filter(pk=new.pk,entry__dictionary=self.dictionary).exists())
        self.assertEqual(mwe_audio.restore(self.owner,run),(0,0))

    def test_sentence_set_followup_uses_its_word_units_without_substitutions(self):
        from community_dictionary.models import SentenceWord
        word,old=self.seed();self.seed('another expression')
        sentence,_=self.seed('Katten sträcker ut sig',kind='sentence')
        SentenceWord.objects.create(sentence_text=sentence.current_text,word_entry=word,
            word_text=word.current_text,surface='sträcker ut sig')
        data={'token':uuid.uuid4(),'name':'Original sentence trial','scope':'sentences',
              'sampling':'all','size':30,'allow_visitors':False}
        before=ev.create_set(self.owner,self.dictionary,data)
        before.closed_at=timezone.now();before.save()
        after=ev.create_set(self.owner,self.dictionary,{**data,'token':uuid.uuid4(),'scope':'word_audio','based_on':before})
        self.assertEqual(list(after.items.values_list('entry_id',flat=True)),[word.pk])
        Entry.objects.filter(pk=word.pk).update(archived=True)
        with self.assertRaises(Conflict):
            ev.create_set(self.owner,self.dictionary,{**data,'token':uuid.uuid4(),'scope':'word_audio','based_on':before})
