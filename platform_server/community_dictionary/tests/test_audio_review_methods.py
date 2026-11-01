"""Mixed repair candidates: approved cost/scope, real adapters and private publication."""
import uuid
from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase, override_settings
from community_dictionary import audio_review as review, carrier, port_tasks, porting, sentence_forms as sf
from community_dictionary.models import Contribution, PortRun
from community_dictionary.services import Conflict
from community_dictionary.storage import path_for
from projects.models import CreditLedgerEntry
from . import test_audio_groups as fixtures
from .test_mwe_audio import carrier_wave
from .test_tts_guidance import provider


@override_settings(OPENAI_API_KEY='fixture-only', CREDITS_ENABLED=True,
    COMMUNITY_DICTIONARY_PORT_WINDOW=2, PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class MixedReviewTests(TestCase):
    setUp = fixtures.GroupReviewTests.setUp
    seed = fixtures.GroupReviewTests.seed
    old_audio = fixtures.GroupReviewTests.old_audio
    mark = fixtures.GroupReviewTests.mark
    approve = fixtures.GroupReviewTests.approve
    synthesis = staticmethod(fixtures.GroupReviewTests.synthesis)
    finish = fixtures.GroupReviewTests.finish
    choose = fixtures.GroupReviewTests.choose
    url = fixtures.GroupReviewTests.url
    form = fixtures.GroupReviewTests.form
    pair = fixtures.GroupReviewTests.pair
    audio_group = fixtures.GroupReviewTests.audio_group
    mark_all = fixtures.GroupReviewTests.mark_all

    def quote(self, count=3, method='mixed'):
        return review.quote(self.owner, self.dictionary, uuid.uuid4(), count, generation_method=method)

    def test_plan_prices_and_approval_match_actual_methods_not_double_count(self):
        self.mark(self.seed().current_text)
        for count in (3, 5):
            run = self.quote(count)
            clips = run.items.get().result['clips']
            self.assertEqual([c['method'] for c in clips], ['guidance','carrier','guidance','carrier','guidance'][:count])
            self.assertEqual(run.estimated_usd, sum(Decimal(c['estimate']) for c in clips))
            self.assertEqual(run.allowance_usd, sum(Decimal(c['allowance']) for c in clips))
            self.assertEqual(clips[1]['estimate'], str(porting.money(carrier.estimate('queue','French'))))
            self.assertEqual(clips[1]['allowance'], str(porting.money(carrier.estimate('queue','French',allowance=True))))
            self.assertEqual(run.prices['carrier_recipe'], carrier.VERSION)
            response = self.client.get(self.url('run',run.pk))
            self.assertEqual(response.context['total'], count)
            self.assertEqual(response.context['carrier_count'], count//2)
        self.assertFalse(CreditLedgerEntry.objects.exists())
        self.approve(run)
        carried, guided = self.finish(run)
        self.assertEqual((carried.call_count,guided.call_count),(2,3))
        self.assertTrue(run.settled)
        self.assertEqual(run.charged_usd,Decimal('.005'))
        self.assertEqual(CreditLedgerEntry.objects.count(),2)

    def test_new_forms_default_to_mixed_but_old_posts_keep_guidance_scope(self):
        self.mark(self.seed().current_text)
        response = self.client.get(self.url())
        self.assertContains(response, '<option value="mixed" selected>Both methods</option>', html=True)
        data = {'action':'quote','token':str(uuid.uuid4()),'candidates':'3'}
        # Old rendered forms carried no generation method.
        response = self.client.post(self.url(),data)
        self.assertEqual(response.status_code,302)
        old = PortRun.objects.get(pk=data['token'])
        self.assertEqual({c['method'] for c in old.items.get().result['clips']},{'guidance'})
        for method,count in [('mixed',1),('invalid',3)]:
            with self.assertRaises(Conflict):self.quote(count,method)
        run = self.quote(1,'carrier')
        self.assertEqual(run.items.get().result['clips'][0]['method'],'carrier')
        self.approve(run);self.finish(run)

    def test_real_adapters_use_same_voice_and_publish_only_extracted_audio(self):
        entry = self.seed(); old = self.old_audio(entry);self.mark(entry.current_text)
        run = self.quote(2); self.approve(run)
        with provider([carrier_wave(),carrier_wave()]) as (coach,speech,_), \
             patch.object(port_tasks,'send'),self.captureOnCommitCallbacks(execute=True):
            for _ in range(3):
                port_tasks.dispatch(str(run.pk))
                for item in run.items.filter(status='queued'):port_tasks.process_item(item.pk)
        run.refresh_from_db();self.assertEqual(run.status,'complete')
        self.assertEqual(coach.call_count,1)
        self.assertEqual([c.kwargs['input'] for c in speech.call_args_list],['queue','On commence. queue. C’est fini.'])
        self.assertEqual({c.kwargs['voice'] for c in speech.call_args_list},{'marin'})
        item = run.items.get();clip = item.result['clips'][1]
        extracted, full = [path_for(clip[k]).read_bytes() for k in ('path','full_path')]
        self.assertLess(len(extracted),len(full))
        old.refresh_from_db();self.assertEqual(old.status,'accepted')
        self.assertContains(self.client.get(self.url('run',run.pk)),'Hear the full carrier recording')
        url = self.url('preview',run.pk,item.pk,clip['id'])+'?full=1'
        response = self.client.get(url,HTTP_RANGE='bytes=0-43')
        self.assertEqual(response.status_code,206)
        self.assertEqual(b''.join(response.streaming_content),full[:44]);response.close()
        self.client.force_login(self.member);self.assertEqual(self.client.get(url).status_code,404)
        self.client.force_login(self.owner)
        saved = self.choose(run,1);audio = Contribution.objects.get(pk=saved['accepted_audio_id'])
        self.assertEqual(path_for(audio.file_path).read_bytes(),extracted)
        self.assertEqual(audio.provenance['generation_method'],'carrier')
        self.assertEqual(audio.provenance['instructions_version'],carrier.VERSION)
        self.assertTrue(audio.provenance['pronunciation_approved'])
        self.assertNotEqual(audio.file_path,clip['path'])
        self.assertEqual(self.client.get(url).status_code,404)  # Accepted previews are private history.

    def test_failed_carrier_keeps_full_take_private_and_other_candidates_usable(self):
        self.mark(self.seed().current_text)
        def fails(text,**kwargs):
            self.synthesis(text,**kwargs)
            raise carrier.ExtractionFailed('test extraction failure')
        run = self.quote();self.approve(run)
        carried,guided = self.finish(run,carrier_fn=fails)
        self.assertEqual((carried.call_count,guided.call_count),(1,2))
        item = run.items.get();clip = item.result['clips'][1]
        self.assertEqual(clip['status'],'failed');self.assertNotIn('path',clip)
        url = self.url('preview',run.pk,item.pk,clip['id'])
        self.assertEqual(self.client.get(url).status_code,404)
        response = self.client.get(url+'?full=1');self.assertEqual(response.status_code,200);response.close()
        with self.assertRaises(Conflict):self.choose(run,1)
        self.assertContains(self.client.get(self.url('run',run.pk)),'Carrier audio could not be cleanly extracted')
        self.choose(run,0)
        self.assertTrue(run.settled)

    def test_group_carrier_acceptance_preserves_each_forms_translation_and_scope(self):
        first,second = self.pair()
        for part in (first,second):self.old_audio(part.entry,part)
        self.mark_all(first)
        run = self.quote();self.assertEqual(len(run.items.get().snapshot['words']),2)
        self.assertEqual(len(run.items.get().result['clips']),3)
        self.approve(run);self.finish(run)
        saved = self.choose(run,1)
        self.assertEqual(len(saved['accepted_audio_ids']),2)
        for part in (first,second):
            audio = sf.audio(part)
            self.assertTrue(sf.pronunciation_approved(audio))
            self.assertEqual(audio.provenance['generation_method'],'carrier')
            self.assertTrue(sf.audio_current(audio))
        second.refresh_from_db();self.assertEqual(second.meaning,'is (a colour)')

    def test_unsupported_carrier_falls_back_only_in_mixed_and_is_counted_honestly(self):
        self.dictionary.language='Spanish';self.dictionary.save()
        self.mark(self.seed('pan','bread').current_text)
        self.assertEqual([v for v,_ in review.method_choices(self.dictionary)],['guidance'])
        with self.assertRaises(Conflict):self.quote(1,'carrier')
        run=self.quote()
        self.assertNotIn('carrier_recipe',run.prices)
        self.assertEqual({c['method'] for c in run.items.get().result['clips']},{'guidance'})
        self.assertEqual(self.client.get(self.url('run',run.pk)).context['carrier_count'],0)
        self.approve(run);carried,guided=self.finish(run)
        carried.assert_not_called();self.assertEqual(guided.call_count,3)

    def test_new_round_has_fresh_approval_and_carrier_recipe_is_pinned(self):
        entry = self.seed();self.mark(entry.current_text)
        old=self.quote(1,'guidance');self.approve(old);self.finish(old)
        item=old.items.get()
        run=review.quote_more(self.owner,self.dictionary,old.pk,item.pk,entry.current_text_id,
            uuid.uuid4(),5,generation_method='mixed')
        self.assertEqual(run.options['previous_run'],str(old.pk))
        self.assertEqual(run.status,'estimate');self.assertFalse(run.reserved_usd)
        self.assertEqual(CreditLedgerEntry.objects.count(),2)
        with patch.object(carrier,'VERSION','changed'):
            with self.assertRaises(Conflict):self.approve(run)
        self.assertEqual(CreditLedgerEntry.objects.count(),2)
        self.approve(run)
        with patch.object(carrier,'VERSION','changed'):
            with self.assertRaises(Conflict):review.current_item(run.items.get())
        self.finish(run)
        self.assertContains(self.client.get(self.url('run',run.pk)),'Carrier phrase with extraction')
        self.assertTrue(path_for(item.result['clips'][0]['path']).exists())
