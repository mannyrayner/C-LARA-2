"""Pictures must teach the accepted lemma/sense, with recoverable paid attempts."""
from datetime import timedelta
import io
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import uuid
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import transaction
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from PIL import Image

from community_dictionary import capture, lemma_images as pictures, practice, public_practice, sentence_forms
from community_dictionary.capture_vocabulary import publish_words
from community_dictionary.models import Contribution, Dictionary, Entry, ImageStudy, ImageWordLink, LemmaImage, Membership
from community_dictionary.storage import path_for
from projects.models import AIUsageCharge


@override_settings(OPENAI_API_KEY='test-key-not-real', CREDITS_ENABLED=False,
    COMMUNITY_DICTIONARY_IMAGE_MODEL='gpt-image-2.5-sunburst',
    COMMUNITY_DICTIONARY_PHOTO_MODEL='gpt-5',
    COMMUNITY_DICTIONARY_IMAGE_ALLOWANCE_USD='0.50', COMMUNITY_DICTIONARY_IMAGE_DAILY_LIMIT=20,
    PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class LemmaImageTests(TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        configured = override_settings(COMMUNITY_DICTIONARY_MEDIA_ROOT=Path(tmp.name))
        configured.enable(); self.addCleanup(configured.disable)
        self.owner = get_user_model().objects.create_user('owner', password='fixture')
        self.member = get_user_model().objects.create_user('member', password='fixture')
        self.outsider = get_user_model().objects.create_user('outsider', password='fixture')
        self.d = Dictionary.objects.create(owner=self.owner, name='Words', language='Swedish',
            explanation_language='English', image_generation_enabled=True)
        Membership.objects.create(dictionary=self.d, user=self.member, accepted=True)
        self.queue = patch.object(pictures, 'queue').start()
        self.addCleanup(patch.stopall)
        buf = io.BytesIO(); Image.new('RGB', (20, 20), 'green').save(buf, 'PNG')
        self.png = buf.getvalue()
        self.client.force_login(self.owner)

    def url(self, name, *args):
        return reverse('community_dictionary:'+name, args=[self.d.pk, *args])

    def word(self, word='katt', meaning='cat'):
        entry = Entry.objects.create(dictionary=self.d, created_by=self.owner)
        capture.component(entry, self.owner, 'word', word, {})
        capture.component(entry, self.owner, 'meaning', meaning, {})
        return entry

    def attempt(self, entry=None):
        entry = entry or self.word()
        with transaction.atomic():
            return pictures.request(entry, self.owner)

    def response(self, suitability='clue'):
        return SimpleNamespace(status='completed', usage=SimpleNamespace(input_tokens=100, output_tokens=50),
            output_text=json.dumps({'suitability': suitability,
                'subject': '' if suitability == 'none' else 'A cat sitting alone, on a plain background.'}))

    def run_job(self, row, suitability='clue', generate=None):
        with patch.object(pictures, 'analyse', return_value=self.response(suitability)) as analysis, \
             patch.object(pictures.images, 'generate', return_value=generate or
                ((self.png, 'image/png', '.png'), {'prompt_tokens':100, 'completion_tokens':1000, 'total_tokens':1100}, '')) as image:
            pictures.run(row.pk, row.revision)
        row.refresh_from_db()
        return analysis, image

    def post_picture(self, entry, **data):
        row = LemmaImage.objects.filter(entry=entry).first()
        quote = self.client.get(self.url('word-picture', entry.pk)).context['generation_quote'] if data.get('action') == 'generate' else ''
        return self.client.post(self.url('word-picture', entry.pk), {
            'submission_id': str(uuid.uuid4()), 'revision': row.revision if row else 0, 'quote': quote, **data})

    def test_generation_and_redelivery_have_one_image_and_one_charge_per_stage(self):
        row = self.attempt()
        analysis, image = self.run_job(row)
        self.assertEqual(row.status, 'ready')
        self.assertTrue(path_for(row.image.file_path).is_file())
        self.assertFalse(row.image.provenance['human_reviewed'])
        self.assertEqual(AIUsageCharge.objects.count(), 2)
        with patch.object(pictures, 'analyse') as again:
            pictures.run(row.pk, row.revision)
            again.assert_not_called()
        self.assertEqual(analysis.call_count, 1)
        self.assertEqual(image.call_count, 1)
        self.assertEqual(AIUsageCharge.objects.count(), 2)
        self.assertEqual(Contribution.objects.filter(kind='image').count(), 1)

    def test_abstract_placeholder_has_no_image_call_or_picture_game(self):
        entry = self.word('eftersom', 'because')
        row = self.attempt(entry)
        _analysis, image = self.run_job(row, 'none')
        image.assert_not_called()
        self.assertEqual(row.status, 'none')
        self.assertEqual(AIUsageCharge.objects.count(), 1)
        self.assertContains(self.client.get(self.url('word', entry.pk)), 'No simple picture')
        self.assertEqual(practice.eligible(practice.catalogue(self.d)[0], 'image-text'), [])

    def test_illustration_is_visible_but_not_a_clue_and_editor_can_override(self):
        row = self.attempt()
        self.run_job(row, 'illustration')
        self.assertEqual(pictures.picture(row.entry)['id'], row.image_id)
        rows, _, before = practice.catalogue(self.d)
        self.assertFalse(rows[0]['image'])
        self.assertEqual(self.post_picture(row.entry, action='clue').status_code, 302)
        rows, _, after = practice.catalogue(self.d)
        self.assertTrue(rows[0]['image'])
        self.assertNotEqual(before, after)
        self.assertEqual(self.post_picture(row.entry, action='none').status_code, 302)
        self.assertEqual(pictures.picture(row.entry)['status'], 'none')

    def test_forms_and_senses_share_only_their_own_lemma_picture(self):
        sentence = Entry.objects.create(dictionary=self.d, created_by=self.owner, entry_type='sentence')
        capture.component(sentence, self.owner, 'word', 'Katterna sover.', {})
        capture.component(sentence, self.owner, 'meaning', 'The cats sleep.', {})
        with transaction.atomic():
            first = publish_words(sentence.current_text, [{'lemma':'katt', 'meaning':'cat',
                'surface':'Katterna', 'form_meaning':'the cats'}], self.owner, {}, [])[0]
        row = self.attempt(first); self.run_job(row)
        form = sentence.contributions.get(kind='form')
        self.assertEqual(sentence_forms.current(form).word_entry_id, first.pk)
        self.assertEqual(Entry.objects.filter(entry_type='word').count(), 1)
        rows = practice.catalogue(self.d)[0]
        self.assertEqual([r['text'] for r in practice.eligible(rows, 'image-text')], ['katt'])
        other_sense = self.word('katt', 'a different meaning')
        self.assertFalse(pictures.picture(other_sense))
        page = self.client.get(self.url('entry', sentence.pk))
        self.assertContains(page, self.url('media', row.image_id))

    def test_automatic_publication_queues_once_and_preserves_existing_pictures(self):
        with self.captureOnCommitCallbacks(execute=True):
            entry = self.word()
        self.assertEqual(LemmaImage.objects.filter(entry=entry).count(), 1)
        self.assertEqual(self.queue.call_count, 1)
        pictures.automatic(entry.pk)
        self.assertEqual(self.queue.call_count, 1)
        other = self.word('hund', 'dog')
        Contribution.objects.create(entry=other, author=self.owner, kind='image', status='accepted', file_path='old.jpg')
        pictures.automatic(other.pk)
        self.assertFalse(LemmaImage.objects.filter(entry=other).exists())
        self.assertNotIn(other, pictures.missing(self.d))

    def test_automatic_generation_respects_owner_optout_and_ai_language(self):
        self.d.automatic_word_images = False; self.d.save()
        entry = self.word()
        pictures.automatic(entry.pk)
        self.assertFalse(LemmaImage.objects.exists())
        self.d.automatic_word_images = True; self.d.language = 'Unsupported fixture language'; self.d.save()
        pictures.automatic(entry.pk)
        self.assertFalse(LemmaImage.objects.exists())

    def test_failed_call_is_not_replayed_and_explicit_retry_is_new_attempt(self):
        row = self.attempt()
        self.run_job(row, generate=(None, {'prompt_tokens':100,'completion_tokens':200}, 'provider_or_image_error'))
        self.assertEqual(row.status, 'failed')
        self.assertEqual(AIUsageCharge.objects.count(), 2)  # returned usage survives failure
        with patch.object(pictures, 'analyse') as again:
            pictures.run(row.pk, row.revision)
            again.assert_not_called()
        self.assertEqual(self.post_picture(row.entry, action='generate', ai_consent='on').status_code, 302)
        row.refresh_from_db(); self.assertEqual(row.revision, 2)
        self.run_job(row)
        self.assertEqual(ImageStudy.objects.count(), 2)

    def test_changed_word_discards_result_but_keeps_accounting(self):
        row = self.attempt()
        def changed(*args):
            Entry.objects.filter(pk=row.entry_id).update(meaning='changed')
            return (self.png, 'image/png', '.png'), {'prompt_tokens':100, 'completion_tokens':200}, ''
        with patch.object(pictures, 'analyse', return_value=self.response()), \
             patch.object(pictures.images, 'generate', side_effect=changed):
            pictures.run(row.pk, row.revision)
        row.refresh_from_db()
        self.assertEqual(row.status, 'failed')
        self.assertFalse(Contribution.objects.filter(kind='image').exists())
        self.assertEqual(AIUsageCharge.objects.count(), 2)

    def test_edit_or_withdrawal_invalidates_existing_game_and_public_clues(self):
        row = self.attempt(); self.run_job(row)
        private_rows, _, before = practice.catalogue(self.d)
        self.assertTrue(private_rows[0]['image'])
        self.assertTrue(public_practice.catalogue(self.d)[0][0]['image'])
        row.image.status = 'withdrawn'; row.image.save()
        private_rows, _, after = practice.catalogue(self.d)
        self.assertFalse(private_rows[0]['image'])
        self.assertNotEqual(before, after)
        self.assertFalse(public_practice.catalogue(self.d)[0][0]['image'])

    def test_backfill_preview_scope_consent_replay_and_preservation(self):
        entries = [self.word(str(i), 'meaning') for i in range(7)]
        page = self.client.get(self.url('word-images'), {'action':'preview', 'limit':5})
        self.assertEqual(len(page.context['candidates']), 5)
        data = {'limit':5, 'quote':page.context['quote'], 'submission_id':str(uuid.uuid4()), 'action':'generate'}
        denied = self.client.post(self.url('word-images'), data)
        self.assertContains(denied, 'Confirm AI processing')
        self.assertFalse(LemmaImage.objects.exists())
        data['ai_consent'] = 'on'
        self.assertEqual(self.client.post(self.url('word-images'), data).status_code, 302)
        self.assertEqual(self.client.post(self.url('word-images'), data).status_code, 302)
        self.assertEqual(LemmaImage.objects.count(), 5)
        self.assertEqual(len(self.client.get(self.url('word-images')).context['candidates']), 2)

    def test_stale_batch_quote_and_stale_editor_form_are_rejected(self):
        entry = self.word()
        page = self.client.get(self.url('word-images'), {'action':'preview', 'limit':5})
        Entry.objects.filter(pk=entry.pk).update(meaning='changed')
        response = self.client.post(self.url('word-images'), {'limit':5, 'quote':page.context['quote'],
            'submission_id':str(uuid.uuid4()), 'action':'generate', 'ai_consent':'on'})
        self.assertContains(response, 'words or meanings changed')
        self.assertFalse(LemmaImage.objects.exists())
        entry.refresh_from_db()
        self.post_picture(entry, action='none')
        stale = self.client.post(self.url('word-picture', entry.pk), {'revision':0,
            'submission_id':str(uuid.uuid4()), 'action':'remove'})
        self.assertContains(stale, 'word picture changed')

    def test_old_worker_cannot_replace_new_manual_decision(self):
        row = self.attempt()
        def decision(*args):
            self.post_picture(row.entry, action='none')
            return (self.png, 'image/png', '.png'), {'prompt_tokens':100,'completion_tokens':200}, ''
        with patch.object(pictures, 'analyse', return_value=self.response()), \
             patch.object(pictures.images, 'generate', side_effect=decision):
            pictures.run(row.pk, row.revision)
        row.refresh_from_db()
        self.assertEqual(row.status, 'none')
        self.assertFalse(Contribution.objects.filter(kind='image').exists())
        self.assertEqual(AIUsageCharge.objects.count(), 2)

    def test_permissions_and_csrf(self):
        entry = self.word()
        for user in (self.member, self.outsider):
            self.client.force_login(user)
            self.assertIn(self.client.get(self.url('word-images')).status_code, (403,404))
            self.assertIn(self.post_picture(entry, action='none').status_code, (403,404))
        from django.test import Client
        secured = Client(enforce_csrf_checks=True); secured.force_login(self.owner)
        self.assertEqual(secured.post(self.url('word-images'), {'action':'resume'}).status_code, 403)

    def test_limits_and_changed_policy_stop_before_paid_work(self):
        row = self.attempt()
        with override_settings(COMMUNITY_DICTIONARY_IMAGE_DAILY_LIMIT=0), patch.object(pictures, 'analyse') as api:
            pictures.run(row.pk, row.revision)
            api.assert_not_called()
        row.refresh_from_db(); self.assertEqual(row.status, 'failed')
        self.assertFalse(ImageStudy.objects.exists())
        other = self.attempt(self.word('hund', 'dog'))
        Dictionary.objects.filter(pk=self.d.pk).update(image_generation_enabled=False)
        with patch.object(pictures, 'analyse') as api:
            pictures.run(other.pk, other.revision)
            api.assert_not_called()

    def test_replacement_upload_and_hiding_require_no_ai(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        entry = self.word()
        with patch.object(pictures, 'analyse') as api:
            result = self.post_picture(entry, action='upload', upload_consent='on',
                photo=SimpleUploadedFile('cat.png', self.png, content_type='image/png'))
            self.assertEqual(result.status_code, 302)
            row = LemmaImage.objects.get(entry=entry)
            self.assertEqual(row.suitability, 'clue')
            self.assertTrue(path_for(row.image.file_path).is_file())
            self.assertEqual(self.post_picture(entry, action='remove').status_code, 302)
            self.assertFalse(practice.catalogue(self.d)[0][0]['image'])
            self.assertNotIn('id', pictures.picture(entry))
            api.assert_not_called()

    def test_backfill_preserves_pending_images_but_skips_accepted_ones(self):
        entry = self.word()
        pending = Contribution.objects.create(entry=entry, author=self.owner, kind='image', status='pending', file_path='pending.jpg')
        self.assertIn(entry, pictures.missing(self.d))
        pending.status='accepted'; pending.save()
        self.assertNotIn(entry, pictures.missing(self.d))

    def test_export_keeps_display_decisions_but_no_private_job_state(self):
        import zipfile
        row = self.attempt(); self.run_job(row)
        row.analysis['PRIVATE_PLAN_MARKER'] = 'PRIVATE_PLAN_MARKER'; row.save()
        abstract = self.attempt(self.word('eftersom', 'because')); self.run_job(abstract, 'none')
        response = self.client.get(self.url('export'))
        with zipfile.ZipFile(io.BytesIO(b''.join(response.streaming_content))) as archive:
            data = archive.read('records.json').decode()
            records = json.loads(data)
            self.assertNotIn('PRIVATE_PLAN_MARKER', data)
            decisions = [r['fields'] for r in records if r['model'] == 'community_dictionary.lemmaimage']
            self.assertEqual(len(decisions), 2)
            self.assertTrue(all(r['study'] is None and r['quote'] == {} and r['analysis'] == {} for r in decisions))
            self.assertEqual({r['status'] for r in decisions}, {'ready','none'})

    def test_example_withdrawal_keeps_independent_lemma_image(self):
        from community_dictionary.collections import withdraw
        entry = self.word()
        sentence = Entry.objects.create(dictionary=self.d, created_by=self.owner, entry_type='sentence')
        capture.component(sentence, self.owner, 'word', 'Katten sover.', {})
        capture.component(sentence, self.owner, 'meaning', 'The cat sleeps.', {})
        from community_dictionary.models import SentenceWord
        SentenceWord.objects.create(sentence_text=sentence.current_text, word_entry=entry,
            word_text=entry.current_text, surface='Katten')
        row = self.attempt(entry); self.run_job(row)
        self.assertNotIn('example_ids', row.analysis)
        self.assertNotIn('examples', row.analysis)
        self.assertFalse(row.image.source_dependencies.filter(source_id=sentence.current_text_id).exists())
        withdraw(self.owner, [sentence.current_text_id], moderator_dictionary=self.d)
        self.assertTrue(practice.catalogue(self.d)[0][0]['image'])

    def test_compiled_french_and_slovak_picture_controls(self):
        entry = self.word()
        for language, label, allowance in [('fr', 'Image du mot', 'Quota habituel'), ('sk', 'Obrázok slova', 'Bežný limit')]:
            self.client.post(reverse('community_dictionary:set-language'), {'language':language})
            self.assertContains(self.client.get(self.url('word-picture', entry.pk)), label)
            preview = self.client.get(self.url('word-images'), {'action':'preview', 'limit':1})
            self.assertContains(preview, allowance)
            self.assertContains(preview, 'name="extra_allowance"')

    def test_failed_regeneration_preserves_existing_picture_and_clue(self):
        row = self.attempt(); self.run_job(row)
        previous = row.image_id
        self.assertEqual(self.post_picture(row.entry, action='generate', ai_consent='on').status_code, 302)
        row.refresh_from_db()
        self.assertEqual(pictures.picture(row.entry)['id'], previous)
        self.run_job(row, generate=(None, {}, 'provider_or_image_error'))
        self.assertEqual(row.status, 'failed')
        self.assertEqual(pictures.picture(row.entry)['id'], previous)
        self.assertTrue(practice.catalogue(self.d)[0][0]['image'])

    def test_preview_and_refresh_give_feedback_without_starting_generation(self):
        for word in ['katt','hund','fisk']:
            self.word(word, word)
        page = self.client.get(self.url('word-images'))
        self.assertContains(page, 'No word-picture batch has been started')
        self.assertNotContains(page, 'name="action" value="generate"')
        for _ in range(2):
            preview = self.client.get(self.url('word-images'), {'action':'preview', 'limit':2})
            self.assertContains(preview, 'Preview ready. Selected word pages: 2.')
            self.assertContains(preview, '2. Approve and generate pictures')
            self.assertContains(preview, 'name="action" value="generate"')
            self.assertEqual(len(preview.context['candidates']), 2)
        refreshed = self.client.get(self.url('word-images'), {'refresh':1})
        self.assertContains(refreshed, 'Progress updated.')
        self.assertContains(refreshed, 'No word-picture batch has been started')
        self.assertContains(refreshed, '?refresh=1#word-image-progress')
        self.assertNotContains(refreshed, 'This field is required.')
        self.assertFalse(LemmaImage.objects.exists())
        self.assertFalse(ImageStudy.objects.exists())
        self.assertFalse(AIUsageCharge.objects.exists())
        self.queue.assert_not_called()

    def test_start_confirmation_preserves_approval_errors_and_shows_queued_words(self):
        self.word()
        page = self.client.get(self.url('word-images'), {'action':'preview', 'limit':1})
        data = {'limit':1, 'quote':page.context['quote'], 'submission_id':str(uuid.uuid4()), 'action':'generate'}
        denied = self.client.post(self.url('word-images'), data)
        self.assertContains(denied, 'Confirm AI processing')
        self.assertContains(denied, '2. Approve and generate pictures')
        data.update(ai_consent='on', quote=denied.context['quote'])
        started = self.client.post(self.url('word-images'), data, follow=True)
        self.assertContains(started, 'Your word-picture batch has started.')
        self.assertContains(started, 'Queued: 1')
        self.assertContains(started, 'Progress updated.')
        self.assertNotContains(started, 'No word-picture batch has been started')
        self.assertNotContains(started, 'This field is required.')
        self.assertEqual(LemmaImage.objects.count(), 1)

    def test_resume_empty_and_failed_progress_are_explicit_and_read_only(self):
        self.word()
        empty = self.client.post(self.url('word-images'), {'action':'resume', 'submission_id':str(uuid.uuid4())}, follow=True)
        self.assertContains(empty, 'There are no unstarted word-picture requests to resume.')
        row = self.attempt()
        row.status = 'failed'; row.analysis = {'error':'Insufficient credit for this word picture.'}; row.save()
        failed = self.client.get(self.url('word-images'), {'refresh':1})
        self.assertContains(failed, 'Failed: 1')
        self.assertContains(failed, 'Insufficient credit for this word picture.')
        self.assertContains(failed, 'No word-picture requests are currently running.')
        self.assertFalse(ImageStudy.objects.exists())
        self.queue.assert_not_called()

    def test_empty_and_translated_preview_states_are_visible(self):
        empty = self.client.get(self.url('word-images'), {'action':'preview', 'limit':5})
        self.assertContains(empty, 'No missing word pictures are available to preview.')
        self.assertNotContains(empty, 'name="action" value="generate"')
        self.word()
        for language, label in [('fr', 'Aperçu prêt.'), ('sk', 'Náhľad je pripravený.')]:
            self.client.post(reverse('community_dictionary:set-language'), {'language':language})
            preview = self.client.get(self.url('word-images'), {'action':'preview', 'limit':1})
            self.assertContains(preview, label)


    def batch_data(self, limit=5, **changes):
        page = self.client.get(self.url('word-images'), {'action':'preview', 'limit':limit})
        return {'limit':limit, 'quote':page.context['quote'], 'submission_id':str(uuid.uuid4()),
            'action':'generate', 'ai_consent':'on', **changes}

    def test_planner_receives_only_lemma_and_translation_even_with_legacy_sentence_data(self):
        self.d.language = 'German'; self.d.save()
        for lemma, sense, scene in [('Himmel','sky','Vier Flugzeuge fliegen am Himmel.'),
                ('vier','four','Vier Flugzeuge fliegen am Himmel.'),
                ('Muster','pattern','Der Teller hat blaue Muster.'),
                ('blau','blue','Der Teller hat blaue Muster.'),
                ('Teller','plate','Der Teller hat blaue Muster.')]:
            row = self.attempt(self.word(lemma, sense))
            row.analysis = {'examples':[scene], 'example_ids':[999]}
            with patch.object(pictures.photo_ai, '_openai_client') as client:
                api = client.return_value.__enter__.return_value.responses.create
                pictures.analyse(row, 'fixture-key')
                payload = json.loads(api.call_args.kwargs['input'])
                self.assertEqual(payload, {'lemma':lemma, 'sense':sense,
                    'language':'German', 'explanation_language':'English'})
                self.assertNotIn(scene, api.call_args.kwargs['input'])

    def test_limit_blocked_words_return_to_backfill_after_an_increased_limit(self):
        with override_settings(COMMUNITY_DICTIONARY_IMAGE_DAILY_LIMIT=1):
            completed = self.attempt(); self.run_job(completed)
            blocked = self.attempt(self.word('hund','dog'))
            analysis, image = self.run_job(blocked)
            analysis.assert_not_called(); image.assert_not_called()
            self.assertEqual(blocked.status, 'failed')
            self.assertIsNone(blocked.study_id)
            self.assertEqual(list(pictures.missing(self.d)), [blocked.entry])
            page = self.client.get(self.url('word-images'), {'action':'preview','limit':5})
            self.assertContains(page, 'Remaining: 0.')
            self.assertContains(page, '>Retry</span>')
        with override_settings(COMMUNITY_DICTIONARY_IMAGE_DAILY_LIMIT=2):
            data = self.batch_data()
            started = self.client.post(self.url('word-images'), data, follow=True)
            self.assertContains(started, 'batch has started')
            blocked.refresh_from_db()
            self.assertEqual(blocked.revision, 2)
            self.run_job(blocked)
            self.assertEqual(blocked.status, 'ready')
            self.assertEqual(ImageStudy.objects.count(), 2)
            self.assertFalse(pictures.missing(self.d).exists())
            completed.refresh_from_db(); self.assertEqual(completed.status, 'ready')

    @override_settings(COMMUNITY_DICTIONARY_IMAGE_DAILY_LIMIT=1)
    def test_temporary_allowance_runs_only_the_approved_batch_without_changing_normal_limit(self):
        completed = self.attempt(); self.run_job(completed)
        words = [self.word('hund','dog'), self.word('fisk','fish')]
        data = self.batch_data(limit=2)
        denied = self.client.post(self.url('word-images'), data)
        self.assertContains(denied, 'exceeds the remaining daily image allowance')
        self.assertEqual(LemmaImage.objects.count(), 1)
        data.update(extra_allowance='on', quote=denied.context['quote'])
        started = self.client.post(self.url('word-images'), data, follow=True)
        self.assertContains(started, 'batch has started')
        self.assertEqual(self.client.post(self.url('word-images'), data).status_code, 302)
        self.assertEqual(LemmaImage.objects.count(), 3)
        for word in words:
            row = LemmaImage.objects.get(entry=word)
            self.run_job(row); self.assertEqual(row.status, 'ready')
            with patch.object(pictures, 'analyse') as again:
                pictures.run(row.pk, row.revision)
                again.assert_not_called()
        self.assertEqual(ImageStudy.objects.count(), 3)
        self.assertEqual(AIUsageCharge.objects.count(), 6)
        self.assertEqual(pictures.daily_usage(self.d,self.owner)['limit'], 1)
        unapproved = self.attempt(self.word('mus','mouse'))
        analysis, image = self.run_job(unapproved)
        analysis.assert_not_called(); image.assert_not_called()
        self.assertEqual(unapproved.status, 'failed')
        self.assertEqual(ImageStudy.objects.count(), 3)

    @override_settings(COMMUNITY_DICTIONARY_IMAGE_DAILY_LIMIT=1)
    def test_single_word_retry_can_use_an_explicit_temporary_allowance(self):
        used = self.attempt(); self.run_job(used)
        entry = self.word('hund','dog')
        denied = self.post_picture(entry, action='generate', ai_consent='on')
        self.assertContains(denied, 'exceeds the remaining daily image allowance')
        self.assertFalse(LemmaImage.objects.filter(entry=entry).exists())
        started = self.post_picture(entry, action='generate', ai_consent='on', extra_allowance='on')
        self.assertEqual(started.status_code, 302)
        row = LemmaImage.objects.get(entry=entry); self.run_job(row)
        self.assertEqual(row.status, 'ready')

    def test_temporary_allowance_cannot_be_copied_to_another_attempt_or_used_after_expiry(self):
        from django.core import signing
        from community_dictionary.services import Conflict
        with transaction.atomic():
            first = pictures.request(self.word(), self.owner, extra_allowance=True)
            second = pictures.request(self.word('hund','dog'), self.owner, extra_allowance=True)
        second.quote['daily_allowance'] = first.quote['daily_allowance']; second.save()
        analysis, image = self.run_job(second)
        analysis.assert_not_called(); image.assert_not_called()
        self.assertEqual(second.status,'failed')
        with patch('django.core.signing.time.time', return_value=0):
            first.quote['daily_allowance'] = signing.dumps({'dictionary':self.d.pk, 'user':self.owner.pk,
                'attempt':first.pk,'revision':first.revision}, salt=pictures.ALLOWANCE_SALT)
        first.save()
        analysis, image = self.run_job(first)
        analysis.assert_not_called(); image.assert_not_called()
        self.assertEqual(first.status,'failed')
        self.assertFalse(ImageStudy.objects.exists())
        self.assertFalse(AIUsageCharge.objects.exists())
        with transaction.atomic():
            third = pictures.request(self.word('fisk','fish'), self.owner, extra_allowance=True)
        third.revision += 1; third.save()
        with self.assertRaises(Conflict): pictures.temporary_allowance(third)

    def test_only_owners_can_approve_extra_allowance_and_zero_limit_still_pauses_requests(self):
        membership = Membership.objects.get(dictionary=self.d, user=self.member)
        membership.role='editor'; membership.save()
        self.word(); self.client.force_login(self.member)
        page = self.client.get(self.url('word-images'), {'action':'preview','limit':1})
        self.assertNotContains(page, 'name="extra_allowance"')
        denied = self.client.post(self.url('word-images'), self.batch_data(1, extra_allowance='on'))
        self.assertContains(denied,'requires a dictionary owner')
        self.assertFalse(LemmaImage.objects.exists())
        self.client.force_login(self.owner)
        with override_settings(COMMUNITY_DICTIONARY_IMAGE_DAILY_LIMIT=0):
            denied = self.client.post(self.url('word-images'), self.batch_data(1, extra_allowance='on'))
            self.assertContains(denied,'paused by the server')
            self.assertFalse(LemmaImage.objects.exists())
        membership.role='co_owner'; membership.save(); self.client.force_login(self.member)
        started = self.client.post(self.url('word-images'), self.batch_data(1, extra_allowance='on'))
        self.assertEqual(started.status_code,302)
        row=LemmaImage.objects.get(); self.assertEqual(row.requested_by,self.member)
        self.run_job(row); self.assertEqual(row.status,'ready')

    def test_recovery_keeps_existing_pictures_manual_choices_and_running_attempts(self):
        good = self.attempt(); self.run_job(good)
        self.post_picture(good.entry, action='generate', ai_consent='on')
        good.refresh_from_db(); self.run_job(good, generate=(None, {}, 'provider_or_image_error'))
        self.assertEqual(good.status,'failed')
        deliberate = self.word('eftersom','because'); self.post_picture(deliberate,action='none')
        hidden = self.word('båt','boat'); self.post_picture(hidden,action='remove')
        self.attempt(self.word('hund','dog'))
        failed = self.attempt(self.word('fisk','fish')); self.run_job(failed,generate=(None,{},'provider_or_image_error'))
        self.assertEqual(list(pictures.missing(self.d)),[failed.entry])
        self.assertTrue(pictures.picture(good.entry)['id'])
        data=self.batch_data()
        failed.revision+=1; failed.save()
        changed=self.client.post(self.url('word-images'),data)
        self.assertContains(changed,'attempt changed')
        failed.refresh_from_db(); self.assertEqual(failed.status,'failed')

    def test_temporary_allowance_still_requires_sufficient_credit(self):
        with transaction.atomic():
            row = pictures.request(self.word(), self.owner, extra_allowance=True)
        with patch.object(pictures, 'credits_enabled', return_value=True), \
             patch.object(pictures, 'get_user_balance_usd', return_value=0):
            analysis, image = self.run_job(row)
        analysis.assert_not_called(); image.assert_not_called()
        self.assertEqual(row.status, 'failed')
        self.assertIn('Insufficient credit', row.analysis['error'])
        self.assertFalse(ImageStudy.objects.exists())
        self.assertFalse(AIUsageCharge.objects.exists())
