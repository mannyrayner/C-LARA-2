import copy
from datetime import timedelta
import uuid
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from community_dictionary import capture, refresh, sentence_forms
from community_dictionary.models import Contribution, Entry, PictureCapture, SentenceWord, VocabularyState
from community_dictionary.services import Conflict
from . import test_picture_capture as fixtures


@override_settings(OPENAI_API_KEY='test-only', CREDITS_ENABLED=False,
    PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class RefreshTests(TestCase):
    def setUp(self):
        fixtures.PictureCaptureTests.setUp(self)
        self.client.force_login(self.owner)
        self.entry = Entry.objects.create(dictionary=self.d, created_by=self.owner, entry_type='sentence')
        old = capture.component(self.entry, self.owner, 'word', fixtures.RESULT['sentence'], {})
        capture.component(self.entry, self.owner, 'meaning', fixtures.RESULT['translation'], {})
        from community_dictionary.capture_vocabulary import publish_words
        words = copy.deepcopy(fixtures.RESULT['words'])
        words[0]['form_meaning'] = 'the cat'
        publish_words(old, words, self.owner, {}, [])
        self.old_words = list(SentenceWord.objects.filter(sentence_text=old).values_list('word_entry_id', flat=True))
        capture.component(self.entry, self.owner, 'word', 'Katten ligger på bordet.', {})
        self.words = copy.deepcopy(words)
        self.words[-1].update(surface='bordet', lemma='bord', meaning='table', form_meaning='the table')
        self.analyser = patch('community_dictionary.port_vocabulary_ai.analyse',
            side_effect=lambda *a, **k: fixtures.response({'words': self.words})).start()
        self.queue = patch('community_dictionary.refresh.queue').start()

    def url(self, name, *args):
        return reverse('community_dictionary:'+name, args=[self.d.pk, *args])

    def page(self):
        return self.client.get(self.url('refresh-start', self.entry.pk))

    def start(self, **extra):
        page = self.page()
        data = {'permission': 'on', 'quote': page.context['form']['quote'].value(),
                'submission_id': str(uuid.uuid4()), **extra}
        result = self.client.post(self.url('refresh-start', self.entry.pk), data)
        self.assertEqual(result.status_code, 302, result.content[:1000])
        return PictureCapture.objects.get(pk=result.url.strip('/').split('/')[-1])

    def edit(self, **extra):
        url = self.url('contribute', self.entry.pk)+'?wording=1'
        page = self.client.get(url)
        return self.client.post(url, {'submission_id': str(uuid.uuid4()), 'edit_text': '1',
            'word': self.entry.word, 'meaning': self.entry.meaning, 'category': '', 'publish_now': 'on',
            'base_version': self.entry.text_version, 'text_snapshot': page.context['form']['text_snapshot'].value(), **extra})

    def test_edit_immediately_offers_update_but_not_for_unchanged_text_or_category(self):
        self.assertEqual(self.edit(word='Katten ligger på mattan.').url, self.url('refresh-start', self.entry.pk))
        self.entry.refresh_from_db()
        self.assertEqual(self.edit(category='home').url, self.url('entry', self.entry.pk))
        self.assertEqual(self.edit(meaning='The cat rests on a mat.').url, self.url('refresh-start', self.entry.pk))
        self.assertFalse(PictureCapture.objects.exists())
        self.analyser.assert_not_called()

    def test_prompt_visible_persistent_action_no_get_calls_or_processing_without_permission(self):
        page = self.page()
        self.assertContains(page, 'Update words and audio to match your edit?')
        self.assertContains(page, 'Not now')
        self.assertIn('no-store', page['Cache-Control'])
        entry_page = self.client.get(self.url('entry', self.entry.pk))
        self.assertContains(entry_page, 'Update words and audio')
        self.client.post(self.url('refresh-start', self.entry.pk), {
            'quote': page.context['form']['quote'].value(), 'submission_id': uuid.uuid4()})
        self.assertFalse(PictureCapture.objects.exists())
        self.analyser.assert_not_called()

    def test_fixed_sentence_refresh_reuses_words_retains_old_entries_and_never_translates(self):
        text_id, meaning_id = self.entry.current_text_id, self.entry.current_meaning_id
        study = self.start(); refresh.run(study.pk); study.refresh_from_db(); self.entry.refresh_from_db()
        self.assertEqual(study.status, 'saved')
        self.assertEqual((self.entry.current_text_id, self.entry.current_meaning_id), (text_id, meaning_id))
        self.assertEqual(self.entry.word, 'Katten ligger på bordet.')
        self.ai.assert_not_called()
        data = self.analyser.call_args.args[0]
        self.assertEqual(data['sentence'], self.entry.word)
        self.assertEqual(data['translation'], self.entry.meaning)
        self.assertIn('soffa', [w['lemma'] for w in data['vocabulary']])
        current = list(SentenceWord.objects.filter(sentence_text=self.entry.current_text).select_related('word_entry'))
        self.assertEqual({x.word_entry.word for x in current}, {'katt', 'ligga', 'på', 'bord'})
        self.assertEqual(Entry.objects.filter(pk__in=self.old_words, archived=False).count(), 4)
        self.assertEqual(sum(x.word_entry_id in self.old_words for x in current), 3)
        self.assertTrue(refresh.port_vocabulary.current_state(self.entry))
        self.assertTrue(study.speech.filter(entry=self.entry, status='ready').exists())
        self.assertTrue(study.speech.filter(kind='form', status='ready').exists())
        self.assertNotContains(self.client.get(self.url('entry', self.entry.pk)), 'Vocabulary needs updating')
        self.assertContains(self.client.get(self.url('refresh-detail', study.pk)), 'Words and audio are up to date')

    def test_current_audio_and_manually_corrected_forms_are_kept(self):
        from community_dictionary.capture_vocabulary import publish_words
        publish_words(self.entry.current_text, self.words, self.owner, {}, [])
        link = SentenceWord.objects.get(sentence_text=self.entry.current_text, surface='Katten')
        form = sentence_forms.find(link)
        corrected = sentence_forms.publish(link, 'the kitten', self.owner, {'human_edit': True}, replace=form.pk)
        self.words[0]['lemma'] = 'KATT'  # A model's case variation must not replace the human form.
        audio = Contribution.objects.create(entry=self.entry, author=self.owner, controlled_by=self.owner,
            kind='audio', status='accepted', file_path='existing.wav', provenance={'origin': 'synthetic',
                'source_text': self.entry.word, 'source_meaning_id': self.entry.current_meaning_id, 'language': 'Swedish'})
        study = self.start(); refresh.run(study.pk)
        self.assertFalse(study.speech.filter(entry=self.entry, kind='entry').exists())
        self.assertTrue(Contribution.objects.filter(pk=audio.pk, status='accepted').exists())
        link.refresh_from_db()
        self.assertEqual(sentence_forms.find(link).pk, corrected.pk)
        self.assertEqual(sentence_forms.find(link).meaning, 'the kitten')

    def test_repeated_taps_and_worker_redelivery_do_not_repeat_paid_work(self):
        first = self.start(); second = self.start()
        self.assertEqual(first.pk, second.pk)
        refresh.run(first.pk); count = self.tts.call_count
        from projects.models import AIUsageCharge
        charges = AIUsageCharge.objects.count()
        self.assertEqual(AIUsageCharge.objects.filter(request_type__startswith=f'capture:{first.pk}:speech:').count(), count)
        refresh.run(first.pk)
        self.assertEqual(self.analyser.call_count, 1)
        self.assertEqual(self.tts.call_count, count)
        self.assertEqual(AIUsageCharge.objects.count(), charges)
        third = self.start()
        self.assertEqual(first.pk, third.pk)

    def test_permissions_and_generic_capture_endpoints_cannot_reinterpret_refresh(self):
        study = self.start()
        generic = self.client.get(self.url('capture-detail', study.pk))
        self.assertEqual(generic.status_code, 404)
        capture.prepare(study.pk); self.ai.assert_not_called()
        with self.assertRaises(Conflict): capture.publish(study.pk, self.owner)
        self.client.force_login(self.user)
        self.assertEqual(self.page().status_code, 404)
        self.assertEqual(self.client.get(self.url('refresh-detail', study.pk)).status_code, 404)
        self.client.force_login(self.outsider)
        self.assertEqual(self.page().status_code, 404)

    def test_changed_sentence_after_quote_cannot_start_or_publish(self):
        quote = self.page().context['form']['quote'].value()
        capture.component(self.entry, self.owner, 'word', 'Katten ligger på mattan.', {})
        result = self.client.post(self.url('refresh-start', self.entry.pk),
            {'quote': quote, 'permission': 'on', 'submission_id': uuid.uuid4()})
        self.assertContains(result, 'sentence or settings changed')
        self.assertFalse(PictureCapture.objects.exists())
        capture.component(self.entry, self.owner, 'word', 'Katten ligger på bordet.', {})
        study = self.start()
        before = SentenceWord.objects.count()
        def changed(*args, **kwargs):
            capture.component(self.entry, self.owner, 'word', 'Katten sover.', {})
            return fixtures.response({'words': self.words})
        self.analyser.side_effect = changed
        refresh.run(study.pk); study.refresh_from_db()
        self.assertEqual(study.status, 'failed')
        self.assertEqual(SentenceWord.objects.count(), before)
        self.assertFalse(VocabularyState.objects.exists())

    def test_failure_and_uncertain_claim_are_not_replayed_automatically(self):
        study = self.start(); self.analyser.side_effect = TimeoutError
        refresh.run(study.pk); refresh.run(study.pk); study.refresh_from_db()
        self.assertEqual(study.status, 'failed'); self.assertEqual(self.analyser.call_count, 1)
        study = self.start(); study.status = 'processing'; study.created_at = timezone.now()-timedelta(minutes=16); study.save()
        refresh.run(study.pk); self.assertEqual(self.analyser.call_count, 1)
        refresh.recover(study); self.assertEqual(study.status, 'failed')
        self.assertContains(self.client.get(self.url('refresh-detail', study.pk)), 'Review a fresh estimate')

    def test_audio_failure_can_retry_missing_audio_without_reextracting_words(self):
        study = self.start(); self.tts.side_effect = TimeoutError
        refresh.run(study.pk); study.refresh_from_db()
        self.assertEqual(study.status, 'saved'); self.assertTrue(capture.failed_audio(study))
        self.tts.side_effect = fixtures.speech
        self.assertEqual(self.client.post(self.url('refresh-action', study.pk),
            {'action': 'retry-audio', 'submission_id': uuid.uuid4()}).status_code, 409)
        result = self.client.post(self.url('refresh-action', study.pk),
            {'action': 'retry-audio', 'permission': 'on', 'submission_id': uuid.uuid4()})
        self.assertEqual(result.status_code, 302)
        refresh.run(study.pk)
        self.assertFalse(capture.failed_audio(study)); self.assertEqual(self.analyser.call_count, 1)

    def test_revoke_or_settings_change_prevents_further_requests(self):
        study = self.start(); self.d.capture_revision += 1; self.d.save()
        refresh.run(study.pk); self.analyser.assert_not_called(); self.tts.assert_not_called()
        self.assertEqual(self.client.get(self.url('refresh-detail', study.pk)).status_code, 409)

    def test_igbo_refresh_keeps_correction_and_uses_frozen_google_audio_policy(self):
        self.d.language = 'Igbo'; self.d.save()
        capture.component(self.entry, self.owner, 'word', 'A hụrụ okpokoro.', {})
        self.words = [{'surface': 'okpokoro', 'lemma': 'okpokoro', 'meaning': 'table',
                       'existing_id': 0, 'form_meaning': 'table'}]
        policy = {'method': 'google_gemini', 'language': 'Igbo', 'voice': 'Kore', 'version': 'test'}
        with patch('community_dictionary.word_audio.policy', return_value=policy), \
             patch('community_dictionary.google_tts.require_access'), \
             patch('community_dictionary.tts.require_google_credit'), \
             patch('community_dictionary.word_audio.synthesize', side_effect=fixtures.speech) as synthesizer:
            self.assertContains(self.page(), 'Google')
            study = self.start(); refresh.run(study.pk); study.refresh_from_db(); self.entry.refresh_from_db()
            self.assertEqual(study.status, 'saved')
            self.assertEqual(self.entry.word, 'A hụrụ okpokoro.')
            self.assertEqual(self.analyser.call_args.args[0]['sentence'], 'A hụrụ okpokoro.')
            self.assertEqual(SentenceWord.objects.get(sentence_text=self.entry.current_text).word_entry.word, 'okpokoro')
            self.assertTrue(synthesizer.called)
            self.assertTrue(all(c.kwargs['expected'] == policy for c in synthesizer.call_args_list))
            self.assertTrue(any(c.kwargs['speech_kind'] == 'sentence' for c in synthesizer.call_args_list))

    def test_other_editor_cannot_start_a_second_concurrent_paid_refresh(self):
        from community_dictionary.models import Membership
        self.start()
        Membership.objects.filter(dictionary=self.d, user=self.user).update(role='co_owner')
        self.client.force_login(self.user)
        page = self.page()
        result = self.client.post(self.url('refresh-start', self.entry.pk), {
            'permission': 'on', 'quote': page.context['form']['quote'].value(), 'submission_id': uuid.uuid4()})
        self.assertContains(result, 'already running')
        self.assertEqual(PictureCapture.objects.count(), 1)

    def test_later_missing_audio_is_repaired_without_another_word_request(self):
        study = self.start(); refresh.run(study.pk)
        word = Entry.objects.get(dictionary=self.d, word='bord')
        word.contributions.filter(kind='audio').update(status='withdrawn')
        self.assertNotContains(self.client.get(self.url('refresh-detail', study.pk)), 'Words and audio are up to date')
        new = self.start(); self.assertNotEqual(new.pk, study.pk)
        before = self.tts.call_count
        refresh.run(new.pk)
        self.assertEqual(self.analyser.call_count, 1)
        self.assertEqual(self.tts.call_count, before+1)
        self.assertTrue(refresh.audio_complete(self.entry))

    def test_audio_timeout_uses_the_clip_start_instead_of_the_old_capture_age(self):
        study = self.start(); refresh.run(study.pk)
        clip = study.speech.first(); clip.status = 'running'
        clip.report = {'refresh_started_at': timezone.now().isoformat()}; clip.save()
        study.created_at = timezone.now()-timedelta(hours=1); study.save()
        refresh.recover(study); clip.refresh_from_db(); self.assertEqual(clip.status, 'running')
        clip.report = {'refresh_started_at': (timezone.now()-timedelta(minutes=16)).isoformat()}; clip.save()
        refresh.recover(study); clip.refresh_from_db(); self.assertEqual(clip.status, 'failed')

    def test_later_word_correction_is_not_reported_as_a_completed_current_refresh(self):
        study = self.start(); refresh.run(study.pk)
        word = Entry.objects.get(dictionary=self.d, word='bord')
        capture.component(word, self.owner, 'meaning', 'work surface', {})
        page = self.client.get(self.url('refresh-detail', study.pk))
        self.assertNotContains(page, 'Words and audio are up to date')
        self.assertContains(page, 'Vocabulary needs updating')
        new = self.start(); self.assertNotEqual(new.pk, study.pk)
