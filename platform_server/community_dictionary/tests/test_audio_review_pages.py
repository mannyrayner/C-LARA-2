"""Page boundaries, bounded database work and private lexical audit exports."""
import csv
import io
from unittest.mock import patch

from django.db import connection
from django.test import TestCase, RequestFactory, override_settings
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from community_dictionary import audio_review as review, audio_review_pages as pages, sentence_forms as sf
from community_dictionary.audio_review_data import ReviewData
from community_dictionary.models import Contribution, SentenceWord
from community_dictionary.participation import withdraw_all
from . import test_google_word_audio as fixtures


@override_settings(COMMUNITY_DICTIONARY_GOOGLE_TTS_ENABLED=True, OPENAI_API_KEY='fixture-only',
    CREDITS_ENABLED=True, COMMUNITY_DICTIONARY_PORT_WINDOW=2,
    PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class AudioReviewPageTests(TestCase):
    setUp = fixtures.GoogleWordAudioTests.setUp
    seed = fixtures.GoogleWordAudioTests.seed
    audio = fixtures.GoogleWordAudioTests.audio
    quote = fixtures.GoogleWordAudioTests.quote
    approve = fixtures.GoogleWordAudioTests.approve
    finish = fixtures.GoogleWordAudioTests.finish
    synthesis = staticmethod(fixtures.GoogleWordAudioTests.synthesis)

    def url(self, run, format=None):
        return reverse('community_dictionary:audio-review-' + ('download' if format else 'run'),
            args=[self.dictionary.pk, run.pk, *([format] if format else [])])

    def saved_batch(self, count=52):
        # Existing persisted outcomes suffice for progress/rendering; no synthesis.
        for n in reversed(range(count)):
            self.seed(f'mot {n:03}', f'word {n}')
        run = self.quote()
        for item in run.items.all():
            item.result['clips'][0]['status'] = 'ready'
            item.save(update_fields=['result'])
        run.status, run.settled = 'complete', True
        run.save(update_fields=['status', 'settled'])
        return run

    def test_progress_and_estimate_do_not_validate_or_render_words(self):
        run = self.saved_batch(4)
        run.status, run.settled = 'estimate', False
        run.save(update_fields=['status', 'settled'])
        with patch.object(pages, 'ReviewData', side_effect=AssertionError('live sources loaded')):
            response = self.client.get(self.url(run))
            self.assertContains(response, 'Inspect selected words')
            self.assertNotContains(response, 'mot 000')
            run.status = 'running'; run.save(update_fields=['status'])
            item = run.items.first()
            item.result['clips'][0]['status'] = 'failed'; item.invalidated = True
            item.save(update_fields=['result', 'invalidated'])
            response = self.client.get(self.url(run))
            self.assertEqual(response.context['total'], 4)
            self.assertEqual(response.context['finished'], 4)
            self.assertEqual(response.context['failures'], 1)
            self.assertContains(response, 'Remaining: 0')
            self.assertNotContains(response, 'mot 000')
        run.status = 'estimate'; run.save(update_fields=['status'])
        self.assertContains(self.client.get(self.url(run), {'inspect':'1'}), 'mot 001')

    def test_pagination_precedes_validation_and_preserves_alphabetic_order(self):
        run = self.saved_batch()
        with patch.object(review, 'current_item', wraps=review.current_item) as validate:
            response = self.client.get(self.url(run), {'page':2})
        self.assertEqual(validate.call_count, 25)
        self.assertEqual([r['word']['word'] for r in response.context['rows']],
                         [f'mot {n:03}' for n in range(25, 50)])
        self.assertEqual(response.context['total'], 52)
        self.assertContains(response, 'Page 2 of 3')
        self.assertNotContains(response, 'mot 000')
        self.assertContains(response, 'fr-FR-Wavenet-F')
        self.assertEqual(len(self.client.get(self.url(run), {'page':3}).context['rows']), 2)
        self.assertEqual(self.client.get(self.url(run), {'page':'garbage'}).context['paging'].number, 1)
        self.assertEqual(self.client.get(self.url(run), {'page':999}).context['paging'].number, 3)

    def test_query_work_is_batched_for_setup_progress_and_review(self):
        self.seed('premier', 'first')
        with CaptureQueriesContext(connection) as small_setup:
            small = self.quote()
        for n in range(55):
            self.seed(f'mot {n:03}', str(n))
        with CaptureQueriesContext(connection) as large_setup:
            large = self.quote()
        # Bulk writes can grow by SQL parameter-limit chunks, not per word.
        self.assertLessEqual(len(large_setup), len(small_setup) + 4)
        factory = RequestFactory()
        query_counts = []
        for run in [small, large]:
            for item in run.items.all():
                self.assertEqual(set(item.sources.values_list('pk', flat=True)),
                                 review.source_ids(item.snapshot['words']))
            with CaptureQueriesContext(connection) as progress:
                pages.presentation(factory.get('/'), run)
            self.assertEqual(len(progress), 1)
            run.status, run.settled = 'complete', True
            with CaptureQueriesContext(connection) as page_queries:
                pages.presentation(factory.get('/'), run)
            query_counts.append(len(page_queries))
        self.assertEqual(query_counts[0], query_counts[1])
        self.assertLessEqual(query_counts[1], 10)

    def test_bulk_source_checks_match_individual_checks_for_forms_and_audio(self):
        word = self.seed('courir', 'run'); self.audio(word)
        sentence = self.seed('Il court.', 'He runs.', kind='sentence')
        link = SentenceWord.objects.create(sentence_text=sentence.current_text, word_entry=word,
            word_text=word.current_text, surface='court')
        form = sf.publish(link, 'runs', self.owner, {'origin':'synthetic'})
        loaded = ReviewData(self.dictionary)
        for part in [word.current_text, form]:
            self.assertEqual(review.row_for(part, all_words=True),
                             review.row_for(loaded.selected[part.pk], all_words=True, loaded=loaded))
        run = self.quote(); self.approve(run); self.finish(run)
        from community_dictionary.google_word_audio import apply_all
        apply_all(self.owner, run)
        loaded = ReviewData(self.dictionary)
        for part in [word.current_text, form]:
            self.assertEqual(review.row_for(part, all_words=True),
                             review.row_for(loaded.selected[part.pk], all_words=True, loaded=loaded))

    def test_download_has_lemmas_forms_contexts_and_decisions_but_no_private_paths(self):
        word = self.seed('courir', 'run')
        sentence = self.seed('Il court.', 'He runs.', kind='sentence')
        link = SentenceWord.objects.create(sentence_text=sentence.current_text, word_entry=word,
            word_text=word.current_text, surface='court')
        form = sf.publish(link, 'runs', self.owner, {'origin':'synthetic'})
        run = self.quote(); self.approve(run); self.finish(run)
        item = next(i for i in run.items.all() if i.source_entry_id == sentence.pk)
        clip = item.result['clips'][0]
        response = self.client.post(self.url(run), {'action':'note', 'item':item.pk,
            'part':form.pk, 'note':'=à vérifier', 'page':2, 'filter':'awaiting'})
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.endswith(f'?page=2&filter=awaiting&inspect=0#word-{form.pk}'))
        self.assertEqual(self.client.post(self.url(run), {'action':'accept', 'item':item.pk,
            'part':form.pk, 'clip':clip['id']}).status_code, 302)
        download = self.client.get(self.url(run, 'json'))
        self.assertEqual(download.status_code, 200)
        self.assertIn('no-store', download['Cache-Control'])
        data = download.json()
        self.assertEqual(data['summary']['exported_groups'], 2)
        group = next(g for g in data['groups'] if g['representative_part_id'] == form.pk)
        self.assertEqual(group['note'], '=à vérifier')
        self.assertEqual(group['review_state'], 'accepted')
        member = group['members'][0]
        self.assertEqual((member['text'],member['meaning'],member['lemma'],member['lemma_meaning']),
                         ('court','runs','courir','run'))
        self.assertEqual(member['contexts'][0]['sentence'], 'Il court.')
        self.assertEqual(member['contexts'][0]['translation'], 'He runs.')
        self.assertEqual(member['current_audio'][0]['provider'], 'google')
        self.assertTrue(member['current_audio'][0]['pronunciation_approved'])
        self.assertNotIn(clip['path'], download.content.decode())
        self.assertNotIn('report', group['candidates'][0])
        content = self.client.get(self.url(run, 'csv')).content.decode('utf-8-sig')
        rows = list(csv.DictReader(io.StringIO(content)))
        self.assertEqual(len(rows), 2)
        self.assertEqual(next(r for r in rows if r['text']=='court')['note'], "'=à vérifier")
        self.assertEqual(len(self.client.get(self.url(run), {'filter':'accepted'}).context['rows']), 1)
        self.assertEqual(len(self.client.get(self.url(run), {'filter':'awaiting'}).context['rows']), 1)

    def test_all_pages_exported_and_changed_sources_omitted(self):
        run = self.saved_batch(28)
        item = run.items.first()
        hidden = item.snapshot['words'][0]['word']
        Contribution.objects.filter(pk=item.snapshot['words'][0]['id']).update(word='changed')
        data = self.client.get(self.url(run, 'json'), {'page':1, 'filter':'failed'}).json()
        self.assertEqual(data['summary']['exported_groups'], 27)
        self.assertEqual(data['summary']['omitted_unavailable_groups'], 1)
        self.assertNotIn(hidden, str(data))
        self.assertNotIn('changed', [m['text'] for g in data['groups'] for m in g['members']])
        self.assertEqual(len(self.client.get(self.url(run), {'filter':'failed'}).context['rows']), 0)
        self.assertEqual(self.client.get(self.url(run, 'xml')).status_code, 404)

    def test_withdrawal_and_new_human_audio_protect_review_and_export(self):
        word = self.seed('secret', 'secret meaning', author=self.member)
        run = self.quote(); self.approve(run); self.finish(run)
        withdraw_all(self.member, self.dictionary.pk, self.dictionary.membership_revision)
        self.assertEqual(self.client.get(self.url(run, 'json')).json()['groups'], [])
        self.assertNotContains(self.client.get(self.url(run)), 'secret meaning')
        word2 = self.seed('public', 'another meaning')
        run2 = self.quote(); self.approve(run2); self.finish(run2)
        self.audio(word2, human=True)
        self.assertEqual(self.client.get(self.url(run2, 'json')).json()['groups'], [])

    def test_export_and_notes_require_owner_and_notes_check_current_sources(self):
        word = self.seed(); run = self.quote(); self.approve(run); self.finish(run)
        item = run.items.get()
        payload = {'action':'note', 'item':item.pk, 'part':word.current_text_id, 'note':'x'*1001}
        self.assertEqual(self.client.post(self.url(run), payload).status_code, 409)
        self.client.force_login(self.member)
        self.assertIn(self.client.get(self.url(run, 'json')).status_code, [403,404])
        self.assertIn(self.client.post(self.url(run), payload).status_code, [403,404])
        self.client.logout()
        self.assertEqual(self.client.get(self.url(run, 'csv')).status_code, 302)
        self.client.force_login(self.owner)
        Contribution.objects.filter(pk=word.current_text_id).update(word='different')
        self.assertEqual(self.client.post(self.url(run), {**payload, 'note':'hello'}).status_code, 409)
