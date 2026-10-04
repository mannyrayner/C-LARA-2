"""Offline wiring/quality-gate tests. These do not assess spoken pronunciation."""
from contextlib import contextmanager
from decimal import Decimal
import io
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch
import uuid
import wave

from django.test import TestCase, SimpleTestCase, override_settings

from community_dictionary import tts, pronunciation, port_tasks, porting
from community_dictionary.models import AudioStudy, Contribution, ContributionDependency, PortItem
from community_dictionary.services import add_contributions, Conflict
from community_dictionary.collections import withdraw
from community_dictionary.storage import path_for
from projects.models import AIUsageCharge, CreditAccount
from . import test_entry_media as media_tests, test_porting as port_tests


def quiet(level=0):
    out = io.BytesIO()
    with wave.open(out, 'wb') as stream:
        stream.setparams((1, 2, 24000, 0, 'NONE', 'not compressed'))
        stream.writeframes(int(level).to_bytes(2, 'little', signed=True)*2400)
    return out.getvalue()


def guidance(**extra):
    return SimpleNamespace(status='completed', usage=SimpleNamespace(input_tokens=400, output_tokens=120),
        output_text=json.dumps({'definition': 'animal domestique qui miaule', 'ipa': 'ʃa',
            'sound_hint': 'ch comme chaque, a ouvert, t final muet', **extra}))


@contextmanager
def provider(outputs=None, coaching=None, streaming=True):
    outputs = iter(outputs if outputs is not None else [media_tests.speech_fixture()[0][0]])
    def speech(**kwargs):
        data = next(outputs)
        if isinstance(data, Exception):
            raise data
        response = SimpleNamespace(stream_to_file=lambda path: Path(path).write_bytes(data))
        if not streaming:
            return response
        @contextmanager
        def wrapper():
            yield response
        return wrapper()
    create = Mock(side_effect=speech)
    coach = Mock(return_value=guidance()) if coaching is None else coaching
    client = SimpleNamespace(responses=SimpleNamespace(create=coach), audio=SimpleNamespace(speech=SimpleNamespace(
        create=create, with_streaming_response=SimpleNamespace(create=create) if streaming else None)))
    with patch.object(tts, '_openai_client') as factory:
        factory.return_value.__enter__.return_value = client
        yield coach, create, factory


class GuidanceTests(SimpleTestCase):
    def call(self, word='chat', language='fr', **kwargs):
        return tts.synthesize(word, language=language, model=tts.MODEL, voice='marin', api_key='test-only',
            guidance_model='gpt-6-sol', guidance_prices={'input':'2', 'output':'10'}, **kwargs)

    def test_all_probe_homographs_and_nonhomographs(self):
        for lang, words in [('fr','chat lit pain coin'), ('de','die hat war also'),
                            ('sv','barn bad red gift'), ('it','pane cane sale fine')]:
            for word in words.split():
                self.assertEqual(pronunciation.homographs(word, lang), [word])
        for word, lang in [('fromage','fr'),('jardin','fr'),('Katze','de'),('schön','de'),
                           ('katt','sv'),('sjö','sv'),('gatto','it'),('letto','it'),('chat','en')]:
            self.assertEqual(pronunciation.homographs(word,lang), [])
        self.assertEqual(pronunciation.homographs('« CHAT! »','French'), ['chat'])
        self.assertIn('dogs', pronunciation.homographs('dogs','fr'))
        self.assertEqual(pronunciation.homographs('schön', 'de'), pronunciation.homographs('scho\u0308n','de'))
        self.assertNotIn('lit', pronunciation.homographs('literie', 'fr'))

    def test_enrichment_keeps_exact_input_and_uses_private_structured_call(self):
        for streaming in [True, False]:
            with self.subTest(streaming=streaming), provider(streaming=streaming) as (coach, speech, factory):
                report = {}
                prepared, _ = self.call(meaning='cat', meaning_language='English', report=report)
                self.assertEqual(prepared[0], media_tests.speech_fixture()[0][0])
                self.assertEqual(coach.call_count, 1)
                request = coach.call_args.kwargs
                self.assertFalse(request['store'])
                self.assertEqual(json.loads(request['input'])['meaning'], 'cat')
                self.assertNotIn('image', json.loads(request['input']))
                self.assertTrue(request['text']['format']['strict'])
                self.assertEqual(speech.call_args.kwargs['input'], 'chat')
                self.assertIn('ʃa', speech.call_args.kwargs['instructions'])
                self.assertIn('animal domestique', speech.call_args.kwargs['instructions'])
                self.assertEqual(report['english_homographs'], ['chat'])
                self.assertEqual(report['guidance_cost_usd'], '0.002000')
                self.assertEqual(factory.call_args.kwargs['max_retries'], 0)

    def test_nonhomograph_and_english_skip_guidance(self):
        for word, language in [('häst','sv'), ('chat','en')]:
            with provider() as (coach, speech, _):
                self.call(word, language)
                coach.assert_not_called()
                self.assertEqual(speech.call_count, 1)

    def test_quiet_result_retried_once_without_repeating_guidance(self):
        with provider([quiet(12), media_tests.speech_fixture()[0][0]]) as (coach, speech, _):
            report = {}; gate = Mock()
            self.call(report=report, before_request=gate)
            self.assertEqual(coach.call_count, 1); self.assertEqual(speech.call_count, 2)
            self.assertEqual(gate.call_count, 3)
            self.assertEqual([a['outcome'] for a in report['attempts']], ['near_silent','usable'])
            one = tts.estimate_cost('chat'+report['instructions'], .1)
            self.assertEqual(Decimal(report['speech_cost_usd']), 2*one)
            self.assertGreater(tts.report_cost(report), 2*one)

    def test_two_quiet_results_stop_with_both_costs(self):
        with provider([quiet(), quiet(31)]) as (coach, speech, _):
            report = {}
            with self.assertRaises(tts.SilentAudio): self.call(report=report)
            self.assertEqual(speech.call_count, 2); self.assertEqual(coach.call_count, 1)
            self.assertFalse(report['uncertain_cost'])
            self.assertEqual(len(report['attempts']), 2)

    def test_timeout_or_bad_audio_is_not_retried(self):
        for output in [TimeoutError('private-secret'), b'not a wave']:
            with provider([output]) as (_, speech, _):
                report = {}
                with self.assertRaises(Exception): self.call(report=report)
                self.assertEqual(speech.call_count, 1)
                self.assertTrue(report['uncertain_cost'])
                self.assertNotIn('private-secret', json.dumps(report))

    def test_bad_or_failed_guidance_does_not_send_speech(self):
        for coach in [Mock(side_effect=TimeoutError), Mock(return_value=guidance(ipa=''))]:
            with provider(coaching=coach) as (_, speech, _):
                with self.assertRaises((TimeoutError, ValueError)): self.call()
                speech.assert_not_called()

    def test_authority_loss_before_retry_stops_spending(self):
        with provider([quiet(), media_tests.speech_fixture()[0][0]]) as (_, speech, _):
            gate = Mock(side_effect=[None,None,Conflict('withdrawn')])
            with self.assertRaises(Conflict): self.call(before_request=gate)
            self.assertEqual(speech.call_count, 1)


@override_settings(OPENAI_API_KEY='test-only', CREDITS_ENABLED=False)
class GuidanceFlowTests(TestCase):
    url = media_tests.EntryMediaTests.url
    generate = media_tests.EntryMediaTests.generate
    audio_save = media_tests.EntryMediaTests.audio_save

    def setUp(self):
        media_tests.EntryMediaTests.setUp(self)
        patch.stopall()  # Exercise the real synthesis adapter with only HTTP mocked below.
        self.dictionary.language = 'French'; self.dictionary.save()
        add_contributions(self.entry, self.owner, {'word':'chat','meaning':'cat',
            'base_version':self.entry.text_version,'meaning_base_version':self.entry.meaning_version}, [], publish=True)
        self.entry.refresh_from_db()

    def test_entry_preview_save_warning_and_provenance(self):
        with provider() as (coach, speech, _):
            token = uuid.uuid4(); self.generate(token); self.generate(token)
        self.assertEqual(coach.call_count, 1); self.assertEqual(speech.call_count, 1)
        study = AudioStudy.objects.get()
        self.assertEqual(study.status, 'ready')
        self.assertContains(self.client.get(self.url('audio-study',study.pk)), 'Check pronunciation')
        self.assertEqual(self.audio_save(study).status_code, 302)
        audio = Contribution.objects.get(kind='audio')
        self.assertEqual(audio.provenance['synthesis']['english_homographs'], ['chat'])
        self.assertTrue(ContributionDependency.objects.filter(derived=audio,source_id=self.entry.current_meaning_id).exists())
        self.assertContains(self.client.get(self.url('entry',self.entry.pk)), 'Check pronunciation')
        self.assertContains(self.client.get(self.url('word',self.entry.pk)), 'Check pronunciation')

    @override_settings(CREDITS_ENABLED=True)
    def test_failed_silent_generation_charges_once_and_cannot_be_saved(self):
        CreditAccount.objects.update_or_create(user=self.owner, defaults={'balance_usd':1})
        with provider([quiet(),quiet(12)]) as (_, speech, _):
            token = uuid.uuid4(); self.generate(token); self.generate(token)
        study = AudioStudy.objects.get()
        self.assertEqual(study.status, 'failed'); self.assertFalse(study.file_path)
        self.assertEqual(speech.call_count, 2)
        self.assertEqual(AIUsageCharge.objects.count(), 1)
        self.assertEqual(AIUsageCharge.objects.get().cost_usd, study.cost_usd)
        self.assertEqual(self.audio_save(study).status_code, 409)

    def test_withdrawn_meaning_discards_preview_and_guidance(self):
        with provider(): self.generate()
        study = AudioStudy.objects.get(); original_path = study.file_path
        with self.captureOnCommitCallbacks(execute=True):
            withdraw(self.owner, [self.entry.current_meaning_id])
        study.refresh_from_db()
        self.assertEqual(study.status, 'discarded')
        self.assertEqual(study.synthesis, {}); self.assertEqual(study.source_meaning, '')
        self.assertFalse(path_for(original_path).exists())

    def test_changed_meaning_blocks_saving_old_preview(self):
        with provider(): self.generate()
        study = AudioStudy.objects.get()
        add_contributions(self.entry,self.owner,{'meaning':'another sense',
            'meaning_base_version':self.entry.meaning_version},[],publish=True)
        self.assertEqual(self.audio_save(study).status_code,409)

    def test_withdrawal_during_guidance_stops_speech_and_drops_private_hints(self):
        def answer(**kwargs):
            withdraw(self.owner, [self.entry.current_meaning_id])
            return guidance()
        with provider(coaching=Mock(side_effect=answer)) as (_, speech, _):
            self.generate()
        speech.assert_not_called()
        study = AudioStudy.objects.get()
        self.assertEqual(study.status, 'discarded')
        self.assertFalse(study.synthesis); self.assertFalse(study.source_meaning)

    def test_withdrawal_removes_saved_guidance_derived_audio_from_shared_entry(self):
        with provider(): self.generate()
        self.audio_save(AudioStudy.objects.get())
        audio = Contribution.objects.get(kind='audio')
        withdraw(self.owner, [self.entry.current_meaning_id])
        audio.refresh_from_db()
        self.assertTrue(audio.entry.dictionary.personal)
        self.assertFalse(self.entry.contributions.filter(pk=audio.pk).exists())


@override_settings(OPENAI_API_KEY='fixture-only', CREDITS_ENABLED=True,
    COMMUNITY_DICTIONARY_PHOTO_MODEL='gpt-6-sol', COMMUNITY_DICTIONARY_PORT_WINDOW=2)
class PortGuidanceTests(TestCase):
    setUp = port_tests.PortingTests.setUp
    url = port_tests.PortingTests.url
    post = port_tests.PortingTests.post
    create_entry = port_tests.PortingTests.create_entry
    seed = port_tests.PortingTests.seed
    quote = port_tests.PortingTests.quote
    approve = port_tests.PortingTests.approve

    def test_port_cost_guidance_retry_review_and_saved_provenance(self):
        self.seed(); run = self.approve(self.quote(language='French')); item = run.items.get()
        with patch.object(port_tasks.port_ai,'translate',return_value=port_tests.response('chat')), \
                provider([quiet(),media_tests.speech_fixture()[0][0]]) as (coach,speech,_), \
                patch.object(port_tasks,'dispatch'):
            port_tasks.process_item(item.pk); port_tasks.process_item(item.pk)
        item.refresh_from_db()
        self.assertEqual(item.status,'ready'); self.assertTrue(item.file_path)
        self.assertEqual(coach.call_count,1); self.assertEqual(speech.call_count,2)
        self.assertEqual(item.audio_cost,tts.report_cost(item.result['tts_synthesis']))
        self.assertLess(item.audio_cost+item.translation_cost,item.allowance_usd)
        self.assertContains(self.client.get(self.url('port-review',run.pk,item.pk)), 'Check pronunciation')
        values = {k:item.result[k] for k in ['word','meaning','category']}
        entry = porting.save_item(self.owner,item.pk,values)
        audio = entry.contributions.get(kind='audio')
        self.assertEqual(audio.provenance['synthesis']['english_homographs'],['chat'])

    def test_failed_port_speech_keeps_text_and_known_costs(self):
        self.seed(); run = self.approve(self.quote(language='French')); item = run.items.get()
        with patch.object(port_tasks.port_ai,'translate',return_value=port_tests.response('chat')), \
                provider([quiet(),quiet()]), patch.object(port_tasks,'dispatch'):
            port_tasks.process_item(item.pk)
        item.refresh_from_db()
        self.assertEqual(item.status,'ready'); self.assertFalse(item.file_path)
        self.assertEqual(item.result['word'],'chat'); self.assertGreater(item.audio_cost,0)
        self.assertFalse(item.uncertain_cost)

    def test_old_recipe_revisited_but_saved_current_recipe_skipped(self):
        self.seed(); run = self.approve(self.quote(language='French')); item = run.items.get()
        with patch.object(port_tasks.port_ai,'translate',return_value=port_tests.response('chat')), \
                provider(), patch.object(port_tasks,'dispatch'):
            port_tasks.process_item(item.pk)
        item.refresh_from_db()
        porting.save_item(self.owner,item.pk,{k:item.result[k] for k in ['word','meaning','category']})
        # Complete this fixture job before asking for another estimate.
        run.refresh_from_db()
        porting.settle(run)
        update = self.quote(port=run.port)
        self.assertEqual(update.skipped,1); self.assertFalse(update.items.exists())
        from community_dictionary import port_categories
        link = run.port.entry_links.get()
        with patch.object(tts,'INSTRUCTIONS_VERSION','native-language-2'):
            source = link.source
            group = run.category_plan.get(port_categories.key(source.category))
            link.source_digest = port_categories.digest(porting.snapshot(source),group)
            link.save(update_fields=['source_digest'])
        repair = self.quote(port=run.port)
        self.assertEqual(repair.items.count(),1)

    def test_old_approved_job_does_not_gain_unapproved_extra_calls(self):
        self.seed(); run = self.approve(self.quote(language='French')); item = run.items.get()
        run.prices.pop('speech_recipe'); run.save(update_fields=['prices'])
        with patch.object(port_tasks.port_ai, 'translate') as translate, provider() as (coach,speech,_), \
                patch.object(port_tasks, 'dispatch'):
            port_tasks.process_item(item.pk)
        translate.assert_not_called(); coach.assert_not_called(); speech.assert_not_called()
