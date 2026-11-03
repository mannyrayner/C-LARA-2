"""Offline provider-study contracts: independent ratings, blinding and source control."""
import json
import uuid
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from community_dictionary import audio_evaluation as study, homograph_experiments as exp, port_tasks
from community_dictionary.models import (Contribution, EvaluationRating, EvaluationSet,
                                         LanguageCompetence, PortRun)
from community_dictionary.services import Conflict
from community_dictionary.participation import withdraw_all
from projects.models import CreditLedgerEntry
from .test_provider_comparison import ProviderComparisonTests


@override_settings(COMMUNITY_DICTIONARY_GOOGLE_TTS_ENABLED=True,OPENAI_API_KEY='fixture-only',
    CREDITS_ENABLED=True,COMMUNITY_DICTIONARY_PORT_WINDOW=2)
class AudioStudyTests(TestCase):
    seed=ProviderComparisonTests.seed
    approve=ProviderComparisonTests.approve
    finish=ProviderComparisonTests.finish
    synthesis=staticmethod(ProviderComparisonTests.synthesis)

    def setUp(self):
        ProviderComparisonTests.setUp(self)
        self.dictionary.language='English';self.dictionary.explanation_language='French';self.dictionary.save()
        for user in [self.owner,self.member,self.third]:
            LanguageCompetence.objects.create(user=user,language='English',language_key='english',reading=3,listening=3)

    def url(self,name,*args):
        return reverse('community_dictionary:audio-study-'+name,args=[self.dictionary.pk,*args])

    def run_quote(self,words=None,**kwargs):
        entries=words or [self.seed('cat','chat')]
        return exp.quote(self.owner,self.dictionary,uuid.uuid4(),[e.current_text_id for e in entries],
            1,comparison=True,study={'rubric':study.RUBRIC,'name':'English trial','allow_visitors':False},**kwargs)

    def batch(self,words=None,fail=False):
        run=self.run_quote(words)
        self.approve(run)
        def failed(text,**kw):
            kw['before_request']();raise TimeoutError('private')
        self.finish(run,google_fn=failed if fail else None)
        return study.freeze(self.owner,run),run

    def join(self,batch,user=None):
        return study.join(user or self.owner,batch,{'involvement':'yes' if user is None else 'no',
            'equipment':'headphones','prior_exposure':'no'})

    def values(self,session,record,outcome='choose'):
        clips=study.ordered_clips(session,record)
        ready=[c for _,c in clips if c['status']=='ready']
        data={'revision':0,'preference':outcome,'preferred':[ready[0]['id']] if outcome=='choose' else [],
              'preference_comment':''}
        for c in ready:
            data['score_'+c['id']]='ok';data['comment_'+c['id']]=''
        return data

    def test_estimate_is_unpaid_reproducible_and_preparation_has_no_word_list(self):
        entries=[self.seed(w,w) for w in ['cat','dog','table','window']]
        run=self.run_quote(entries,sampling='random',sample_size=3)
        self.assertEqual(run.options['methods'],study.METHODS)
        self.assertEqual(len(run.options['population_ids']),4)
        self.assertTrue(run.options['sampling_seed'])
        self.assertFalse(CreditLedgerEntry.objects.exists())
        response=self.client.get(self.url('prepare',run.pk))
        self.assertContains(response,'3 sampled items')
        self.assertNotContains(response,'<audio')
        with patch.object(exp,'quote') as quote:
            self.assertEqual(self.client.get(self.url('start')).status_code,200)
        quote.assert_not_called()

    def test_google_check_and_failed_approval_stay_on_saved_study_without_charging(self):
        run=self.run_quote()
        problem=exp.google_tts.GoogleAccessError('sign_in','sign-in renewal')
        with patch.object(exp.google_tts,'check_access',side_effect=problem), patch.object(exp.porting,'approve') as approve:
            for action in ['check-google','approve']:
                response=self.client.post(self.url('prepare',run.pk),{'action':action,'approve':'on'})
                self.assertContains(response,'Google connection needs attention')
                self.assertContains(response,'Your study is still saved')
                self.assertContains(response,'sign-in renewal')
                self.assertContains(response,'Check Google connection')
            approve.assert_not_called()
        self.assertFalse(CreditLedgerEntry.objects.exists())
        run.refresh_from_db();self.assertEqual(run.status,'estimate')
        with patch.object(exp.google_tts,'check_access') as check, patch.object(exp.porting,'approve') as approve:
            response=self.client.post(self.url('prepare',run.pk),{'action':'check-google'})
            self.assertContains(response,'Google connection is working')
            check.assert_called_once_with(self.owner,'English',selected_voices=['en-GB-Wavenet-F','en-GB-Neural2-F'])
            approve.assert_not_called()

    def test_connection_check_requires_owner(self):
        run=self.run_quote()
        self.client.force_login(self.member)
        with patch.object(exp.google_tts,'check_access') as check:
            self.assertEqual(self.client.post(self.url('prepare',run.pk),{'action':'check-google'}).status_code,404)
            check.assert_not_called()

    def test_freeze_idempotent_and_does_not_replace_dictionary_recordings(self):
        before=Contribution.objects.count()
        entry=self.seed('cat','chat');count=Contribution.objects.count()
        batch,run=self.batch([entry])
        self.assertGreater(count,before)
        self.assertEqual(Contribution.objects.count(),count)
        self.assertEqual(study.freeze(self.owner,run).pk,batch.pk)
        self.assertEqual(batch.items.count(),1);self.assertEqual(batch.units.count(),3)
        self.assertFalse(batch.closed_at)

    def test_independent_stable_blinding_and_legacy_routes_cannot_reveal(self):
        batch,run=self.batch();record=batch.items.get()
        with patch.object(study.secrets.SystemRandom,'shuffle',side_effect=lambda values:values.reverse()):
            owner=self.join(batch)
        with patch.object(study.secrets.SystemRandom,'shuffle',return_value=None):
            other=self.join(batch,self.member)
        self.assertNotEqual(owner.evaluator_metadata['orders'],other.evaluator_metadata['orders'])
        again=self.join(batch)
        self.assertEqual(owner.evaluator_metadata['orders'],again.evaluator_metadata['orders'])
        response=self.client.get(self.url('item',batch.pk,record.pk))
        self.assertEqual(response.status_code,200)
        for secret in ['google_wavenet','google_neural2','en-US-Wavenet','en-US-Neural2','gpt-4o-mini-tts']:
            self.assertNotContains(response,secret)
        self.assertEqual(self.client.get(self.url('export',batch.pk,'json')).status_code,409)
        with self.assertRaises(Conflict):exp.save_ratings(run.pk,{},reveal=True)
        clip=record.snapshot['clips'][0]
        legacy=reverse('community_dictionary:homographs-media',args=[self.dictionary.pk,run.pk,record.snapshot['port_item'],clip['id']])
        self.assertEqual(self.client.get(legacy).status_code,404)
        self.assertEqual(self.client.get(reverse('community_dictionary:homographs-export',args=[self.dictionary.pk,run.pk])).status_code,409)

    def test_two_raters_correctness_preference_ties_and_exports(self):
        batch,run=self.batch();record=batch.items.get()
        for user in [self.owner,self.member]:
            session=self.join(batch,user);data=self.values(session,record)
            by_method={c['method']:c for c in record.snapshot['clips']}
            data['preferred']=[by_method['google_wavenet']['id']]
            if user==self.member:
                data['score_'+by_method['openai']['id']]='major'
                data['preference']='tie';data['preferred'].append(by_method['google_neural2']['id'])
            study.save(user,batch,record,data)
        data=study.results(batch)
        stats={s['method']:s for s in data['summaries']}
        self.assertEqual(stats['openai']['acceptable_percent'],50)
        self.assertEqual(stats['google_wavenet']['acceptable_percent'],100)
        self.assertEqual(stats['openai']['agreement']['pairs'],1)
        self.assertEqual(stats['openai']['agreement']['exact_percent'],0)
        self.assertEqual(stats['google_wavenet']['sole_preference'],1)
        self.assertEqual(stats['google_wavenet']['tied_preference'],1)
        self.assertEqual(data['paired'][0]['only_b'],1)
        batch.closed_at=timezone.now();batch.save()
        response=self.client.get(self.url('export',batch.pk,'json'))
        self.assertEqual(response.status_code,200)
        exported=response.json()
        self.assertEqual(exported['configuration']['google_voices']['google_neural2'],'en-GB-Neural2-F')
        self.assertEqual(len(exported['sample_manifest']),1)
        self.assertTrue(exported['generation_created_at'])
        self.assertEqual(len(exported['ratings']),6)
        self.assertEqual({r['evaluator'] for r in exported['ratings']},{'R1','R2'})
        self.assertNotIn('path',response.content.decode())
        self.assertContains(self.client.get(self.url('results',batch.pk)),'Google WaveNet')
        self.assertContains(self.client.get(self.url('export',batch.pk,'csv')),'preferred')
        self.client.force_login(self.member)
        self.assertEqual(self.client.get(self.url('export',batch.pk,'json')).status_code,404)

    def test_failed_clips_remain_and_incomplete_preferences_are_separate(self):
        batch,run=self.batch(fail=True);record=batch.items.get();session=self.join(batch)
        self.assertEqual(record.units.filter(missing=True).count(),2)
        study.save(self.owner,batch,record,self.values(session,record))
        data=study.results(batch)
        self.assertEqual(sum(s['generation_failures'] for s in data['summaries']),2)
        self.assertEqual(data['incomplete_preferences'],1)
        self.assertEqual(data['preference_counts']['choose'],0)
        self.assertEqual(EvaluationRating.objects.count(),1)

    def test_stale_save_and_invalid_preference_are_atomic(self):
        batch,run=self.batch();record=batch.items.get();session=self.join(batch)
        data=self.values(session,record);data['preferred']=[]
        with self.assertRaises(Conflict):study.save(self.owner,batch,record,data)
        self.assertFalse(EvaluationRating.objects.exists())
        data=self.values(session,record);study.save(self.owner,batch,record,data)
        with self.assertRaises(Conflict):study.save(self.owner,batch,record,data)
        self.assertEqual(EvaluationRating.objects.count(),3)
        batch.closed_at=timezone.now();batch.save();data['revision']=1
        with self.assertRaises(Conflict):study.save(self.owner,batch,record,data)

    def test_withdrawal_revokes_media_rating_and_export_content(self):
        entry=self.seed('cat','chat',author=self.member)
        batch,run=self.batch([entry]);record=batch.items.get();session=self.join(batch)
        clip=record.snapshot['clips'][0]
        url=self.url('media',batch.pk,record.pk,clip['id'])
        self.assertEqual(self.client.get(url).status_code,200)
        with patch.object(port_tasks,'send'),self.captureOnCommitCallbacks(execute=True):
            withdraw_all(self.member,self.dictionary.pk,self.dictionary.membership_revision)
        self.assertEqual(self.client.get(url).status_code,404)
        with self.assertRaises(Conflict):study.save(self.owner,batch,record,self.values(session,record))
        data=study.results(batch)
        self.assertEqual(data['available_items'],0);self.assertEqual(data['unavailable_items'],1)
        self.assertEqual(data['ratings'],[])

    def test_source_edit_refuses_new_ratings(self):
        batch,run=self.batch();record=batch.items.get();session=self.join(batch)
        Contribution.objects.filter(pk=record.snapshot['word']['id']).update(word='changed')
        self.assertEqual(study.available(batch,[record]),{})
        self.assertEqual(self.client.get(self.url('item',batch.pk,record.pk)).status_code,409)

    def test_competence_and_permission_required(self):
        batch,run=self.batch()
        LanguageCompetence.objects.filter(user=self.member).update(listening=0)
        with self.assertRaises(Conflict):self.join(batch,self.member)
        self.client.force_login(self.outsider)
        self.assertEqual(self.client.get(self.url('detail',batch.pk)).status_code,404)
        self.assertEqual(self.client.get(self.url('start')).status_code,404)

    def test_page_flow_and_legacy_evaluation_routes_dispatch_safely(self):
        batch,run=self.batch();record=batch.items.get();session=self.join(batch)
        self.assertEqual(self.client.get(reverse('community_dictionary:evaluation-set',args=[self.dictionary.pk,batch.pk])).status_code,302)
        self.assertContains(self.client.get(reverse('community_dictionary:evaluation-home',args=[self.dictionary.pk])),'English trial')
        response=self.client.post(self.url('item',batch.pk,record.pk),self.values(session,record))
        self.assertEqual(response.status_code,302,response.content)
        self.assertContains(self.client.get(self.url('session',batch.pk)),'1 / 1')
        response=self.client.post(reverse('community_dictionary:evaluation-close',args=[self.dictionary.pk,batch.pk]),{'confirm':'yes'},follow=True)
        self.assertEqual(response.status_code,200,response.content)
        batch.refresh_from_db();self.assertIsNotNone(batch.closed_at)

    def test_study_supplement_does_not_change_existing_english_comparisons(self):
        from community_dictionary import google_tts
        entry=self.seed('window','fenêtre')
        run=self.run_quote([entry])
        self.assertEqual(run.prices['google_voices']['en']['google_neural2'],'en-GB-Neural2-F')
        self.assertNotIn('google_neural2',google_tts.VOICES['en'])
        original=exp.quote(self.owner,self.dictionary,uuid.uuid4(),[entry.current_text_id],1,comparison=True)
        self.assertEqual(original.options['methods'],['openai','google_wavenet'])
        self.approve(original)
        self.assertEqual(original.status,'running')

    def test_anonymous_and_unsigned_consent_cannot_start_session(self):
        batch,run=self.batch()
        self.client.logout()
        self.assertEqual(self.client.get(self.url('detail',batch.pk)).status_code,302)
        self.client.force_login(self.member)
        response=self.client.post(self.url('detail',batch.pk),{'involvement':'no',
            'prior_exposure':'no','equipment':'headphones'})
        self.assertEqual(response.status_code,200)
        self.assertFalse(batch.sessions.exists())

    def test_preparation_requires_billing_approval_and_freeze_before_join(self):
        run=self.run_quote()
        with patch.object(exp.google_tts,'check_access') as provider:
            response=self.client.post(self.url('prepare',run.pk),{'action':'approve'})
        self.assertEqual(response.status_code,409)
        provider.assert_not_called()
        self.assertFalse(CreditLedgerEntry.objects.exists())
        with self.assertRaises(Conflict):study.freeze(self.owner,run)
