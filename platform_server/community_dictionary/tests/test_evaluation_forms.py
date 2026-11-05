"""Forms must be judged from their own frozen audio, with legacy/privacy isolation."""
import csv
import io
import re
from unittest.mock import patch

from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext

from community_dictionary import evaluation as ev, sentence_forms as sf
from community_dictionary.models import Contribution, EvaluationRating, Participation, SentenceWord, WithdrawalHold
from community_dictionary.storage import prepare_upload, write_upload
from . import test_evaluation as fixtures
from .test_workflow import recording


class FormEvaluationTests(TestCase):
    setUp = fixtures.EvaluationTests.setUp
    skills = fixtures.EvaluationTests.skills
    make_entry = fixtures.EvaluationTests.make_entry
    link = fixtures.EvaluationTests.link
    batch = fixtures.EvaluationTests.batch
    start = fixtures.EvaluationTests.start
    item_url = fixtures.EvaluationTests.item_url
    save_data = fixtures.EvaluationTests.save_data
    close = fixtures.EvaluationTests.close

    def form(self, sentence=None, *, audio=True):
        sentence = sentence or self.sentence
        link = SentenceWord.objects.get(sentence_text=sentence.current_text, word_entry=self.word)
        part = sf.publish(link, 'the cat', self.owner, {'origin': 'human'})
        clip = self.clip(part) if audio else None
        return part, clip

    def clip(self, part, **metadata):
        return Contribution.objects.create(entry=part.entry, author=self.owner, kind='audio',
            status='accepted', shared_from=part, provenance={'origin': 'synthetic',
                'sentence_form': part.pk, 'source_text': part.word,
                'language': self.dictionary.language, **metadata},
            **write_upload(prepare_upload(recording(), 'audio'), self.dictionary.pk, []))

    def csv(self, batch):
        response = self.owner_client.get(fixtures.url('evaluation-export', self.dictionary.pk, batch.pk))
        self.assertEqual(response.status_code, 200)
        return list(csv.DictReader(io.StringIO(response.content.decode())))

    def test_correct_audio_targets_and_context_before_question(self):
        part, clip = self.form()
        batch = self.batch(); self.start(batch)
        item = batch.items.get()
        html = self.client.get(self.item_url(batch)).content.decode()
        panels = dict(re.findall(r'<fieldset[^>]*data-evaluation-dimension="([^"]+)"[^>]*>(.*?)</fieldset>', html, re.S))
        form = panels['form_audio'].split('<select')[0]
        for text in ['Katten ligger på soffan.', 'Dictionary lemma:', 'katt', 'Form to listen to:', 'Katten', 'the cat']:
            self.assertIn(text, form)
        media = lambda pid: fixtures.url('evaluation-media', self.dictionary.pk, batch.pk, item.pk, pid)
        self.assertIn(media(clip.pk), form)
        self.assertNotIn(media(clip.pk), panels['sentence_audio'])
        self.assertNotIn(media(clip.pk), panels['word_audio'])
        self.assertIn(media(item.snapshot['words'][0]['audio']['id']), panels['word_audio'])
        self.assertIn(media(item.snapshot['entry']['audio']['id']), panels['sentence_audio'])
        self.assertFalse(batch.units.get(dimension='form_audio').missing)
        self.assertEqual(batch.rubric, 'community-quality-v2')
        response = self.client.get(media(clip.pk)); self.assertEqual(response.status_code, 200); response.close()

    def test_missing_and_stale_form_audio_never_falls_back_to_lemma(self):
        batch = self.batch()
        self.assertTrue(batch.units.get(dimension='form_audio').missing)
        part, _ = self.form(audio=False)
        self.clip(part, source_text='wrong surface')
        self.clip(part, language='French')
        self.clip(part, sentence_form=part.pk + 1000)
        batch = self.batch(); self.start(batch, dims=['form_audio'])
        self.assertTrue(batch.units.get(dimension='form_audio').missing)
        response = self.client.get(self.item_url(batch))
        self.assertContains(response, 'Katten')
        self.assertNotContains(response, '<audio')
        self.assertContains(response, 'Missing material at sampling')
        self.close(batch)
        row = next(r for r in self.csv(batch) if r['dimension'] == 'form_audio')
        self.assertEqual((row['audio_text'], row['audio_contribution_id'], row['score']), ('Katten', '', ''))
        self.assertEqual(row['form_contribution_id'], str(part.pk))

    def test_distinct_occurrences_and_missing_counts_separate_from_lemmas(self):
        self.form()
        second = self.make_entry('Katten springer.', 'The cat runs.')
        self.link(second, self.word, 'Katten')
        batch = self.batch()
        self.assertEqual(batch.units.filter(dimension='word_audio').count(), 1)
        self.assertEqual(batch.units.filter(dimension='form_audio').count(), 2)
        row = next(r for r in ev.result_data(batch)['rows'] if r['dimension'] == 'form_audio')
        self.assertEqual((row['units'], row['missing'], row['unrated']), (2, 1, 1))

    def test_identical_and_discontinuous_forms_are_not_missing_audio(self):
        SentenceWord.objects.filter(sentence_text=self.sentence.current_text).update(surface='KATT')
        batch = self.batch()
        self.assertFalse(batch.units.filter(dimension='form_audio').exists())
        SentenceWord.objects.filter(sentence_text=self.sentence.current_text).update(surface='tar … av')
        batch = self.batch()
        self.assertFalse(batch.units.filter(dimension='form_audio').exists())
        response = self.client.get(fixtures.url('evaluation-set', self.dictionary.pk, batch.pk))
        self.assertNotIn('form_audio', dict(response.context['form'].fields['dimensions'].choices))

    def test_form_changes_stop_new_ratings_but_keep_original_export(self):
        part, clip = self.form()
        batch = self.batch(); self.start(batch, dims=['form_audio'])
        item = batch.items.get()
        self.assertEqual(self.client.post(self.item_url(batch), self.save_data(item, session=batch.sessions.get())).status_code, 302)
        link = SentenceWord.objects.get(sentence_text=self.sentence.current_text, word_entry=self.word)
        sf.publish(link, 'changed gloss', self.owner, {'origin': 'human'}, replace=part.pk)
        self.assertEqual(self.client.get(self.item_url(batch)).status_code, 409)
        self.close(batch)
        row = next(r for r in self.csv(batch) if r['dimension'] == 'form_audio')
        self.assertEqual((row['score'], row['form_translation'], row['audio_contribution_id']), ('ok', 'the cat', str(clip.pk)))
        self.assertEqual(ev.result_data(batch)['changed'], 1)

    def test_new_recording_changes_snapshot_and_form_audio_cannot_be_sentence_audio(self):
        part, clip = self.form()
        batch = self.batch(); self.start(batch)
        replacement = self.clip(part, origin='human')
        self.assertEqual(self.client.get(self.item_url(batch)).status_code, 409)
        fresh = self.batch(); item = fresh.items.get()
        self.assertEqual(item.snapshot['words'][0]['form']['audio']['id'], replacement.pk)
        self.assertNotIn(item.snapshot['entry']['audio']['id'], [clip.pk, replacement.pk])

    def test_form_or_recording_withdrawal_withholds_media_and_export(self):
        part, clip = self.form()
        batch = self.batch(); self.start(batch)
        item = batch.items.get()
        media = fixtures.url('evaluation-media', self.dictionary.pk, batch.pk, item.pk, clip.pk)
        self.close(batch)
        for target in [part, clip]:
            with self.subTest(target=target.pk):
                Contribution.objects.filter(pk=target.pk).update(status='withdrawn')
                self.assertEqual(self.client.get(media).status_code, 404)
                self.assertEqual(self.csv(batch), [])
                Contribution.objects.filter(pk=target.pk).update(status='accepted')
                self.assertTrue(self.csv(batch))

    def test_form_source_controller_and_holds_are_checked_on_every_read(self):
        part, clip = self.form()
        part.controlled_by = self.third; part.save(update_fields=['controlled_by'])
        batch = self.batch(); self.start(batch); item = batch.items.get()
        media = fixtures.url('evaluation-media', self.dictionary.pk, batch.pk, item.pk, clip.pk)
        Participation.objects.create(dictionary=self.dictionary, user=self.third, withdrawn=True)
        self.assertEqual(ev.available_items([item], self.dictionary), set())
        self.assertEqual(self.client.get(media).status_code, 404)
        Participation.objects.filter(dictionary=self.dictionary, user=self.third).update(withdrawn=False)
        self.assertEqual(ev.available_items([item], self.dictionary), {item.pk})
        hold = WithdrawalHold.objects.create(contribution=part,
            participation=Participation.objects.get(dictionary=self.dictionary, user=self.third))
        self.assertEqual(ev.available_items([item], self.dictionary), set())
        hold.delete()
        self.assertEqual(ev.available_items([item], self.dictionary), {item.pk})

    def test_v1_sets_keep_original_projection_and_cannot_add_new_dimension(self):
        batch = self.batch()
        batch.rubric = 'community-quality-v1'; batch.save(update_fields=['rubric'])
        batch.units.filter(dimension='form_audio').delete()
        item = batch.items.get(); item.snapshot = ev.graph(self.dictionary)[item.entry_id]
        item.fingerprint = ev.digest(item.snapshot); item.save()
        self.form()
        response = self.client.get(fixtures.url('evaluation-set', self.dictionary.pk, batch.pk))
        self.assertNotIn('form_audio', dict(response.context['form'].fields['dimensions'].choices))
        self.assertEqual(self.client.post(fixtures.url('evaluation-set', self.dictionary.pk, batch.pk), {
            'dimensions': ['form_audio'], 'involvement': 'no', 'consent': 'on'}).status_code, 200)
        self.assertFalse(batch.sessions.exists())
        self.start(batch, dims=['word_audio'])
        self.assertEqual(self.client.get(self.item_url(batch)).status_code, 200)
        self.assertEqual(ev.result_data(batch)['changed'], 0)
        self.close(batch)
        self.assertFalse(any(r['dimension'] == 'form_audio' for r in self.csv(batch)))

    def test_form_ratings_statistics_and_csv_identify_actual_recording(self):
        part, clip = self.form()
        batch = self.batch(); unit = batch.units.get(dimension='form_audio')
        for user, score in [(self.member, 'ok'), (self.third, 'major')]:
            session = self.start(batch, user, dims=['form_audio'])
            EvaluationRating.objects.create(session=session, unit=unit, score=score)
        self.close(batch)
        row = next(r for r in ev.result_data(batch)['rows'] if r['dimension'] == 'form_audio')
        self.assertEqual((row['units'], row['scored'], row['acceptable_percent'], row['overlap_units'], row['pairs']), (1, 2, 50, 1, 1))
        rows = [r for r in self.csv(batch) if r['dimension'] == 'form_audio']
        self.assertEqual({r['score'] for r in rows}, {'ok', 'major'})
        for r in rows:
            self.assertEqual((r['entry_text'], r['word_text'], r['word_form_in_sentence'], r['audio_text']),
                ('Katten ligger på soffan.', 'katt', 'Katten', 'Katten'))
            self.assertEqual((r['audio_contribution_id'], r['form_contribution_id'], r['form_translation']),
                (str(clip.pk), str(part.pk), 'the cat'))

    def test_bounded_queries_and_target_listening_requirement(self):
        self.form()
        for i in range(10):
            sentence = self.make_entry(f'Katten är här {i}.', 'The cat is here.')
            self.link(sentence, self.word, 'Katten'); self.form(sentence)
        with patch('community_dictionary.tts.synthesize', side_effect=AssertionError('No synthesis')):
            with CaptureQueriesContext(connection) as captured:
                live = ev.graph(self.dictionary, include_forms=True)
        self.assertLessEqual(len(captured), 5)
        self.assertEqual(sum(bool(w.get('form', {}).get('audio')) for s in live.values() for w in s['words']), 11)
        self.skills(self.member, listening=1)
        self.assertNotIn('form_audio', ev.eligible_dimensions(ev.competence_snapshot(self.member, self.dictionary), 'sentences'))
