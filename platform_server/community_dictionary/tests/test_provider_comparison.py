"""No live API calls: source selection, provider routing, billing and hidden labels."""
import csv
import io
import json
import tempfile
import uuid
from pathlib import Path
from decimal import Decimal
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.test import TestCase, SimpleTestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from community_dictionary import google_tts, homograph_experiments as exp, port_tasks, porting, sentence_forms as sf
from community_dictionary.models import Contribution, PortRun, SentenceWord
from community_dictionary.services import Conflict
from community_dictionary.participation import withdraw_all
from projects.models import AIUsageCharge, CreditLedgerEntry
from . import test_homograph_experiments as original
from .test_mwe_audio import carrier_wave


@override_settings(COMMUNITY_DICTIONARY_GOOGLE_TTS_ENABLED=True, OPENAI_API_KEY='fixture-only',
    CREDITS_ENABLED=True, COMMUNITY_DICTIONARY_PORT_WINDOW=2)
class ProviderComparisonTests(TestCase):
    seed = original.ExperimentTests.seed
    approve = original.ExperimentTests.approve
    ratings = original.ExperimentTests.ratings
    url = original.ExperimentTests.url
    synthesis = staticmethod(original.ExperimentTests.synthesis)

    def setUp(self):
        original.ExperimentTests.setUp(self)
        self.owner.is_staff = True
        self.owner.save()
        local = patch.object(google_tts, 'credentials', return_value=Mock())
        local.start(); self.addCleanup(local.stop)

    def quote(self, entries=None, **kwargs):
        entries = entries or [self.seed()]
        return exp.quote(self.owner, self.dictionary, uuid.uuid4(),
                         [e.current_text_id for e in entries], 1, comparison=True, **kwargs)

    def finish(self, run, google_fn=None):
        def google(text, **kw):
            kw['before_request']()
            kw['report'].update(speech_cost_usd=str(google_tts.estimate(text,kw['method'])),
                provider='google', attempts=[{'outcome':'usable'}])
            return (carrier_wave(), 'audio/wav', '.wav'), 3.2
        with patch.object(google_tts, 'synthesize', side_effect=google_fn or google) as call:
            carried, guided = original.ExperimentTests.finish(self,run)
        return call, carried, guided

    def test_quote_accepts_ordinary_words_and_mwes_without_network_or_spending(self):
        words = [self.seed('fromage','cheese'), self.seed('se dresser','stand up')]
        with patch.object(google_tts, 'client') as api:
            run = self.quote(words)
        api.assert_not_called()
        self.assertFalse(CreditLedgerEntry.objects.exists())
        self.assertEqual(run.options['methods'], ['openai','google_wavenet','google_neural2'])
        self.assertEqual(sum(len(i.result['clips']) for i in run.items.all()),6)
        for item in run.items.all():
            self.assertEqual({c['label'] for c in item.result['clips']},{'A','B','C'})
        self.assertContains(self.client.get(self.url('run',run.pk)), 'Google project charges')

    def test_current_openai_routes_and_real_google_tariffs_are_recorded(self):
        run=self.quote([self.seed('fromage','cheese'),self.seed('se dresser','stand up')])
        before=Contribution.objects.count(); self.approve(run)
        google,carried,guided=self.finish(run)
        self.assertEqual((google.call_count,carried.call_count,guided.call_count),(4,1,1))
        self.assertFalse(carried.call_args.kwargs['homograph_experiment'])
        self.assertEqual(Contribution.objects.count(),before)
        self.assertEqual(run.status,'complete');self.assertTrue(run.settled)
        charges=AIUsageCharge.objects.filter(provider='google')
        self.assertEqual(charges.count(),4)
        self.assertEqual(set(charges.values_list('model',flat=True)),{'fr-FR-Wavenet-F','fr-FR-Neural2-F'})
        self.assertEqual(run.charged_usd,porting.money(Decimal('.002')+Decimal(17)*Decimal(20)/1000000))
        self.assertEqual(self.finish(run)[0].call_count,0)

    def test_random_sampling_is_saved_idempotently_and_deduplicates_occurrences(self):
        entries=[self.seed(w,w) for w in ['queue','court','fromage','jardin']]
        self.seed('queue','queue')
        self.assertFalse(exp.comparison_homograph({'word':'de l’autre côté'},'French'))
        token=uuid.uuid4()
        run=exp.quote(self.owner,self.dictionary,token,[],1,comparison=True,sampling='random',sample_size=2)
        again=exp.quote(self.owner,self.dictionary,token,[],1,comparison=True,sampling='random',sample_size=2)
        self.assertEqual(run.pk,again.pk)
        self.assertEqual(run.options['population'],4)
        self.assertEqual(sum(len(i.snapshot['words']) for i in run.items.all()),2)
        challenge=self.quote(entries,sampling='homographs',sample_size=60)
        self.assertEqual({w['word'] for i in challenge.items.all() for w in i.snapshot['words']},{'queue','court'})

    def test_forms_keep_source_sentence_and_invalidation(self):
        word=self.seed('courir','run');sentence=self.seed('Le chien court.','The dog runs.',kind='sentence')
        link=SentenceWord.objects.create(sentence_text=sentence.current_text,word_entry=word,
                                        word_text=word.current_text,surface='court')
        form=sf.publish(link,'runs',self.owner,{'origin':'synthetic'})
        run=exp.quote(self.owner,self.dictionary,uuid.uuid4(),[],1,comparison=True,sampling='forms',sample_size=30)
        self.assertEqual(run.items.get().snapshot['words'][0]['context'],'Le chien court.')
        self.approve(run);self.finish(run)
        Contribution.objects.filter(pk=form.pk).update(meaning='changed')
        self.assertEqual(exp.table(run)[0],[])

    def test_swedish_uses_two_methods_not_nonexistent_neural2(self):
        self.dictionary.language='Swedish';self.dictionary.save()
        run=self.quote([self.seed('katt','cat')]);self.approve(run)
        calls=self.finish(run)
        self.assertEqual(calls[0].call_count,1)
        self.assertEqual(run.options['methods'],['openai','google_wavenet'])

    def test_blinding_ratings_paired_results_and_export(self):
        run=self.quote();self.approve(run);self.finish(run)
        response=self.client.get(self.url('run',run.pk))
        self.assertContains(response,'<th scope="col">C</th>',html=True)
        self.assertNotContains(response,'Google Neural2')
        self.assertNotContains(response,'fr-FR-Neural2-F')
        self.assertNotContains(response,'google_neural2')
        self.assertEqual(self.client.get(self.url('export',run.pk)).status_code,409)
        data=self.ratings(run)
        for clip in run.items.get().result['clips']:
            data['rating_'+clip['id']] = 'major' if clip['method']=='openai' else 'acceptable'
        exp.save_ratings(run.pk,data,reveal=True);run.refresh_from_db()
        self.assertTrue(all(p['google_only']==1 for p in exp.paired_summary(run,exp.table(run)[0])))
        result=self.client.get(self.url('export',run.pk))
        rows=list(csv.DictReader(io.StringIO(result.content.decode('utf-8-sig'))))
        self.assertEqual({r['voice'] for r in rows},{'marin','fr-FR-Wavenet-F','fr-FR-Neural2-F'})
        self.assertEqual({r['sampling'] for r in rows},{'manual'})
        self.assertEqual({r['provider'] for r in rows},{'google','openai'})
        self.assertEqual(len(rows),3)

    def test_nonadmin_and_configuration_changes_block_new_spending(self):
        entry=self.seed();start=reverse('community_dictionary:word-audio-compare',args=[self.dictionary.pk])
        self.assertContains(self.client.get(start),'Check Google access')
        run=self.quote([entry])
        with override_settings(COMMUNITY_DICTIONARY_GOOGLE_TTS_PROJECT='different'):
            with self.assertRaises(Conflict): self.approve(run)
        self.owner.is_staff=False;self.owner.save()
        with self.assertRaises(Conflict): self.quote()
        self.assertEqual(self.client.get(start).status_code,409)

    def test_google_access_check_precedes_reservation_and_unapproved_post_does_not_check(self):
        run=self.quote()
        with patch.object(google_tts,'check_access',side_effect=Conflict('Access unavailable')) as api:
            self.assertEqual(self.client.post(self.url('run',run.pk),{'action':'approve'}).status_code,409)
            api.assert_not_called()
            self.assertEqual(self.client.post(self.url('run',run.pk),{'action':'approve','approve':'on'}).status_code,409)
        self.assertFalse(CreditLedgerEntry.objects.exists())

    def test_google_timeout_is_failed_once_but_other_methods_continue(self):
        def fail(text,**kw):
            kw['before_request']();kw['report']['uncertain_cost']=True
            raise TimeoutError('private-provider-message')
        run=self.quote();self.approve(run);calls=self.finish(run,fail)
        self.assertEqual(calls[0].call_count,2)
        clips=run.items.get().result['clips']
        self.assertEqual(sum(c['status']=='failed' for c in clips),2)
        self.assertEqual(sum(c['status']=='ready' for c in clips),1)
        self.assertEqual(run.status,'complete');self.assertTrue(run.settled)
        self.assertNotIn('private-provider-message',json.dumps(clips))

    def test_cancelled_google_claim_keeps_provider_and_cost_during_recovery(self):
        run=self.quote();self.approve(run)
        item=run.items.get();clip=next(c for c in item.result['clips'] if c['method']=='google_wavenet')
        clip['status']='running';item.status='running'
        item.started_at=timezone.now()-timedelta(minutes=16)
        item.usage={'homograph_claim':{k:clip[k] for k in ['id','allowance','method']}}
        item.save()
        with patch.object(port_tasks,'send'),self.captureOnCommitCallbacks(execute=True):
            porting.cancel(self.owner,run.pk)
            exp.resume(self.owner,run.pk)
        run.refresh_from_db()
        self.assertTrue(run.settled)
        self.assertEqual(run.charged_usd,Decimal(clip['allowance']))
        charge=AIUsageCharge.objects.get(provider='google')
        self.assertEqual(charge.model,'fr-FR-Wavenet-F')
        self.assertEqual(self.finish(run)[0].call_count,0)

    def test_withdrawal_removes_google_clips_and_prevents_publication(self):
        entry=self.seed('queue','tail',author=self.member)
        run=self.quote([entry]);self.approve(run);self.finish(run)
        item=run.items.get()
        with self.assertRaises(Conflict):
            porting.save_item(self.owner,item.pk,{'word':'queue','meaning':'tail','category':''})
        with patch.object(port_tasks,'send'),self.captureOnCommitCallbacks(execute=True):
            withdraw_all(self.member,self.dictionary.pk,self.dictionary.membership_revision)
        item.refresh_from_db();self.assertEqual(item.result,{})
        self.assertEqual(exp.table(run)[0],[])


@override_settings(COMMUNITY_DICTIONARY_GOOGLE_TTS_PROJECT='community-dictionaries-tts')
class GoogleAdapterTests(SimpleTestCase):
    def test_explicit_adc_ignores_legacy_variables_and_rejects_wrong_project(self):
        with tempfile.TemporaryDirectory() as temporary:
            path=Path(temporary)/'adc.json'
            info=dict(type='authorized_user',quota_project_id='community-dictionaries-tts',
                      client_id='fixture',client_secret='fixture',refresh_token='fixture')
            path.write_text(json.dumps(info))
            with override_settings(COMMUNITY_DICTIONARY_GOOGLE_TTS_ADC_FILE=str(path)), \
                 patch.dict('os.environ',{'GOOGLE_APPLICATION_CREDENTIALS':'/bad/old.json','GOOGLE_CREDENTIALS_JSON':'bad'}):
                self.assertEqual(google_tts.credentials().quota_project_id,'community-dictionaries-tts')
                info['quota_project_id']='wrong';path.write_text(json.dumps(info))
                with self.assertRaises(Conflict):google_tts.credentials()

    def test_exact_text_locale_voice_no_carrier_no_retry_and_character_cost(self):
        connection=Mock();connection.synthesize_speech.return_value=SimpleNamespace(audio_content=carrier_wave())
        report={};gate=Mock()
        with patch.object(google_tts,'client',return_value=connection):
            prepared,duration=google_tts.synthesize('four',language='French',method='google_wavenet',report=report,before_request=gate)
        connection.synthesize_speech.assert_called_once_with(request={'input':{'text':'four'},
            'voice':{'name':'fr-FR-Wavenet-F','language_code':'fr-FR'},'audio_config':{'audio_encoding':'LINEAR16'}},retry=None,timeout=60)
        gate.assert_called_once();connection.transport.close.assert_called_once()
        self.assertEqual(Decimal(report['speech_cost_usd']),Decimal('.000016'))
        self.assertFalse(report['uncertain_cost']);self.assertEqual(prepared[1],'audio/wav')

    def test_revocation_gate_prevents_synthesis_and_invalid_audio_keeps_known_cost(self):
        connection=Mock();report={}
        with patch.object(google_tts,'client',return_value=connection):
            with self.assertRaises(Conflict):
                google_tts.synthesize('four',language='French',method='google_wavenet',report=report,
                                      before_request=Mock(side_effect=Conflict('revoked')))
        connection.synthesize_speech.assert_not_called();self.assertFalse(report['uncertain_cost'])
        connection.synthesize_speech.return_value=SimpleNamespace(audio_content=b'invalid')
        with patch.object(google_tts,'client',return_value=connection):
            with self.assertRaises(Exception):
                google_tts.synthesize('four',language='French',method='google_neural2',report=report,before_request=Mock())
        self.assertEqual(Decimal(report['speech_cost_usd']),Decimal('.000064'))
        self.assertFalse(report['uncertain_cost'])
