import json
import os
from pathlib import Path
import shutil
import subprocess
from django.core import signing
from django.test import TestCase, override_settings
from community_dictionary import picture_practice as practice, practice_hints, sentence_forms
from community_dictionary.models import PictureCapture, SentenceWord, ImageWordLink
from community_dictionary.picture_practice_views import SALT
from community_dictionary.services import add_contributions
from community_dictionary.storage import prepare_upload
from projects.models import AIUsageCharge
from . import test_picture_practice as base
from .test_workflow import recording


@override_settings(OPENAI_API_KEY='test-only', CREDITS_ENABLED=False,
    PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class PracticeHintsTests(TestCase):
    url = base.PicturePracticeTests.url
    word = base.PicturePracticeTests.word
    image = base.PicturePracticeTests.image
    start = base.PicturePracticeTests.start
    attempt = base.PicturePracticeTests.attempt
    act = base.PicturePracticeTests.act

    def setUp(self):
        base.PicturePracticeTests.setUp(self)
        entry = self.photo.entry
        entry.entry_type = 'sentence'; entry.save(update_fields=['entry_type'])
        add_contributions(entry, self.owner, {'word': 'Il gatto è sotto la sedia.'}, [], publish=True)
        entry.refresh_from_db()
        self.sentence = entry
        self.words = [self.word('gatto', 'cat'), self.word('sedia', 'chair')]
        for word in self.words:
            SentenceWord.objects.create(sentence_text=entry.current_text, word_entry=word,
                word_text=word.current_text, surface=word.word)
            ImageWordLink.objects.create(image=self.photo, word_entry=word, created_by=self.owner)
        self.clips = [self.clip(e) for e in [entry, *self.words]]
        self.photo.refresh_from_db()

    def clip(self, entry):
        clip = add_contributions(entry, self.owner,
            {'prepared_audio': prepare_upload(recording(), 'audio')}, [], publish=True)[0]
        clip.provenance = {'origin': 'synthetic', 'source_text': entry.word, 'language': self.d.language}
        clip.save(update_fields=['provenance'])
        return clip

    def page(self):
        return self.client.get(self.url('picture-practice')+f'?image={self.photo.pk}')

    def inflected(self):
        add_contributions(self.sentence, self.owner, {'word': 'I gatti dormono sulle sedie.'}, [], publish=True)
        self.sentence.refresh_from_db()
        verb = self.word('dormire', 'sleep')
        forms = []
        for word, surface, meaning in [(self.words[0], 'gatti', 'cats'),
                (self.words[1], 'sedie', 'chairs'), (verb, 'dormono', 'are sleeping')]:
            link = SentenceWord.objects.create(sentence_text=self.sentence.current_text,
                word_entry=word, word_text=word.current_text, surface=surface)
            part = sentence_forms.publish(link, meaning, self.owner, {})
            sentence_forms.publish_audio(part, self.owner, prepare_upload(recording(), 'audio'), [], {})
            forms.append(part)
        self.photo.refresh_from_db()
        self.clip(self.sentence)
        return forms

    def test_inflected_text_gloss_and_audio_lead_with_optional_lemmas(self):
        self.inflected()
        counts = (PictureCapture.objects.count(), AIUsageCharge.objects.count())
        page = self.page(); hints = page.context['hints']
        self.assertTrue(hints['has_dictionary_forms'])
        self.assertContains(page, '<details data-hint-lemmas><summary>Dictionary forms</summary>')
        self.assertEqual({row['text']: row['meaning'] for row in hints['words']},
            {'gatti': 'cats', 'sedie': 'chairs', 'dormono': 'are sleeping'})
        for row in hints['words']:
            self.assertEqual(row['audio'].provenance['source_text'], row['text'])
            self.assertNotEqual(row['text'], row['entry'].word)
        for clip in self.clips[1:]:
            self.assertNotContains(page, self.url('media', clip.pk))
        self.assertEqual((PictureCapture.objects.count(), AIUsageCharge.objects.count()), counts)
        self.review.assert_not_called(); self.asr.assert_not_called(); self.tts.assert_not_called()

    def test_missing_stale_or_withdrawn_form_audio_never_uses_lemma_audio(self):
        forms = self.inflected()
        first = sentence_forms.audio(forms[0]); first.provenance['source_text'] = 'gatto'
        first.save(update_fields=['provenance'])
        second = sentence_forms.audio(forms[1]); second.status = 'withdrawn'; second.save(update_fields=['status'])
        forms[2].status = 'withdrawn'; forms[2].save(update_fields=['status'])
        hints = self.page().context['hints']
        self.assertEqual({row['text'] for row in hints['words']}, {'gatti', 'sedie', 'dormono'})
        self.assertTrue(all(row['audio'] is None for row in hints['words']))
        self.assertEqual(hints['word_audio_count'], 0)
        self.assertEqual(next(row for row in hints['words'] if row['text']=='dormono')['meaning'], '')
        self.assertNotContains(self.page(), 'data-hint-listen="words"')

    def test_separated_expression_does_not_reveal_sentence_through_word_audio(self):
        add_contributions(self.sentence, self.owner, {'word': 'I gatti vanno avanti.'}, [], publish=True)
        self.sentence.refresh_from_db(); self.photo.refresh_from_db()
        word = self.word('andare avanti', 'move forward')
        link = SentenceWord.objects.create(sentence_text=self.sentence.current_text,
            word_entry=word, word_text=word.current_text, surface='vanno … avanti')
        sentence_forms.publish(link, 'are moving forward', self.owner, {})
        whole_sentence = self.clip(self.sentence)
        hints = self.page().context['hints']
        row = next(row for row in hints['words'] if row['entry'].pk == word.pk)
        self.assertEqual(row['text'], 'vanno … avanti')
        self.assertIsNone(row['audio'])
        self.assertEqual(hints['sentence']['audio'].pk, whole_sentence.pk)

    def test_hints_reuse_current_material_without_rows_or_ai_charges(self):
        counts = (PictureCapture.objects.count(), AIUsageCharge.objects.count())
        page = self.page()
        hints = page.context['hints']
        self.assertEqual(hints['sentence']['entry'].pk, self.sentence.pk)
        self.assertEqual([w['entry'].pk for w in hints['words']], [w.pk for w in self.words])
        self.assertEqual(hints['word_audio_count'], 2)
        for clip in self.clips:
            self.assertContains(page, self.url('media', clip.pk))
        self.assertEqual((PictureCapture.objects.count(), AIUsageCharge.objects.count()), counts)
        self.review.assert_not_called(); self.asr.assert_not_called(); self.tts.assert_not_called()

    def test_missing_rejected_archived_stale_and_cross_dictionary_material_is_not_offered(self):
        stale, rejected = self.clips[1:]
        stale.provenance['source_text'] = 'old word'; stale.save(update_fields=['provenance'])
        rejected.status = 'rejected'; rejected.save(update_fields=['status'])
        page = self.page()
        self.assertEqual(page.context['hints']['word_audio_count'], 0)
        self.assertNotContains(page, self.url('media', stale.pk))
        self.assertNotContains(page, self.url('media', rejected.pk))
        self.assertNotContains(page, 'data-hint-listen="words"')
        self.assertContains(page, 'Show words')
        word = self.words[1]; word.archived = True; word.save(update_fields=['archived'])
        other = self.word('SECRET OTHER DICTIONARY', 'private')
        from community_dictionary.models import Dictionary
        other.dictionary = Dictionary.objects.create(owner=self.outsider, name='Other', language='Italian')
        other.save(update_fields=['dictionary'])
        ImageWordLink.objects.create(image=self.photo, word_entry=other, created_by=self.owner)
        self.sentence.current_text.status = 'withdrawn'; self.sentence.current_text.save(update_fields=['status'])
        page = self.page()
        self.assertIsNone(page.context['hints']['sentence'])
        self.assertNotContains(page, self.sentence.word)
        self.assertNotContains(page, other.word)
        self.assertNotContains(page, 'data-hint-reveal="sentence"')
        self.assertEqual([r['entry'].pk for r in page.context['hints']['words']], [self.words[0].pk])

    def test_usage_is_bounded_private_and_preserved_when_revising(self):
        study = self.attempt(hints_used='["words_audio", "words_audio", "sentence_text"]')
        self.assertEqual(study.result['practice']['hints_used'], ['words_audio', 'sentence_text'])
        own = self.client.get(self.url('picture-practice-log')).json()['attempts'][0]
        self.assertEqual(own['hints_used'], ['words_audio', 'sentence_text'])
        self.assertEqual(own['hint_recipe'], practice_hints.VERSION)
        self.client.force_login(self.owner)
        self.assertEqual(self.client.get(self.url('picture-practice-log')+'?shared=1').json()['attempts'], [])
        self.client.force_login(self.user)
        practice.run(study.pk)
        self.assertEqual(self.act(study, 'revise', mode='text', description='Un gatto.',
            feedback_language='English', voice='marin', permission='on',
            quote=signing.dumps(practice.quote(self.user, self.d), salt=SALT)).status_code, 302)
        revised = PictureCapture.objects.latest('created_at')
        self.assertEqual(revised.result['practice']['hints_used'], ['words_audio', 'sentence_text'])
        self.assertEqual(revised.result['practice']['hint_recipe'], practice_hints.VERSION)
        before = PictureCapture.objects.count()
        for invalid in ['["invented"]', '{}', 'null', '"words_text"', '[1]', '[[]]', '["words_text"]'*10]:
            self.assertEqual(self.start(hints_used=invalid).status_code, 200)
        self.assertEqual(PictureCapture.objects.count(), before)
        self.assertIsNone(practice_hints.parse_usage(''))
        self.assertEqual(practice_hints.parse_usage('[]'), [])
        self.assertEqual(practice_hints.parse_usage('["lemmas_text"]'), ['lemmas_text'])

    def test_real_controls_preserve_drafts_and_play_audio_without_revealing_words(self):
        node = shutil.which('node')
        if not node or subprocess.run([node, '-e', "require('jsdom')"], capture_output=True).returncode:
            self.skipTest('Optional jsdom is unavailable')
        root = Path(__file__).resolve().parent.parent
        payload = {'html': self.page().content.decode(), 'missing': '',
            'controller': (root/'static/community_dictionary/picture_practice.js').read_text(),
            'app': (root/'static/community_dictionary/app.js').read_text(),
            'recorder': (root/'static/community_dictionary/recorder.js').read_text()}
        self.clips[1].status = 'withdrawn'; self.clips[1].save(update_fields=['status'])
        self.words[1].archived = True; self.words[1].save(update_fields=['archived'])
        self.sentence.current_text.status = 'withdrawn'; self.sentence.current_text.save(update_fields=['status'])
        payload['missing'] = self.page().content.decode()
        # A separate current sentence exercises the default inflections and
        # optional lemma disclosure with the same production controls.
        self.words[1].archived = False; self.words[1].save(update_fields=['archived'])
        self.inflected()
        payload['inflected'] = self.page().content.decode()
        result = subprocess.run([node, str(Path(__file__).with_name('practice_hints_browser.cjs'))],
            input=json.dumps(payload), text=True, capture_output=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stdout+result.stderr)
