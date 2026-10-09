"""Reading views expose missing work without duplicating or hiding vocabulary."""
from django.test import TestCase

from community_dictionary.models import Entry, ImageWordLink, SentenceWord
from community_dictionary.services import add_contributions
from community_dictionary.storage import prepare_upload
from . import test_entry_media as media
from .test_workflow import recording


class EntryOptionsTests(TestCase):
    setUp = media.EntryMediaTests.setUp
    url = media.EntryMediaTests.url

    def audio(self):
        audio = add_contributions(self.entry, self.owner,
            {'prepared_audio': prepare_upload(recording(), 'audio')}, [], publish=True)[0]
        audio.provenance = {'origin': 'synthetic', 'source_text': self.entry.word,
                            'language': self.dictionary.language, 'voice': 'cedar'}
        audio.save(update_fields=['provenance'])
        return audio

    def reading(self, name='entry'):
        response = self.client.get(self.url(name, self.entry.pk))
        self.assertEqual(response.status_code, 200)
        body = response.content.decode()
        self.assertEqual(body.count('id="entry-options"'), 1)
        return body.split('<details class="panel" id="entry-options">', 1)

    def test_completed_entry_and_word_keep_playback_and_hide_editing(self):
        audio = self.audio()
        for name in ['entry', 'word']:
            with self.subTest(name=name):
                reading, options = self.reading(name)
                self.assertIn(self.url('media', audio.pk), reading)
                self.assertIn('Flag a problem', reading)
                for label in ['Record audio', 'Create spoken audio', 'Edit words', 'Add a photo']:
                    self.assertNotIn('>'+label+'<', reading)
                    self.assertIn('>'+label+'<', options)
                self.assertIn('Cedar', options)

    def test_stale_audio_does_not_hide_completion_actions(self):
        self.audio()
        add_contributions(self.entry, self.owner, {'word': 'en häst'}, [], publish=True)
        self.entry.refresh_from_db()
        for name in ['entry', 'word']:
            reading, _ = self.reading(name)
            self.assertIn('>Record audio<', reading)
            self.assertIn('>Create spoken audio<', reading)

    def test_describing_is_visible_only_until_words_exist(self):
        self.dictionary.sentence_capture_enabled = True
        self.dictionary.save(update_fields=['sentence_capture_enabled'])
        reading, options = self.reading()
        self.assertNotIn('Describe this picture', reading)
        self.assertIn('Describe this picture', options)
        add_contributions(self.entry, self.owner, {'word': '', 'edit_text': True}, [], publish=True)
        self.entry.refresh_from_db()
        reading, _ = self.reading()
        self.assertIn('Describe this picture', reading)
        self.assertIn('>Add words<', reading)

    def test_sentence_and_picture_words_deduplicate_by_entry_not_spelling(self):
        self.entry.entry_type = 'sentence'
        self.entry.save(update_fields=['entry_type'])
        words = []
        for meaning in ['cat', 'online conversation']:
            word = Entry.objects.create(dictionary=self.dictionary, created_by=self.owner)
            add_contributions(word, self.owner, {'word': 'chat', 'meaning': meaning}, [], publish=True)
            word.refresh_from_db()
            words.append(word)
        SentenceWord.objects.create(sentence_text=self.entry.current_text,
            word_entry=words[0], word_text=words[0].current_text, surface='chat')
        for word in words:
            ImageWordLink.objects.create(image=self.image, word_entry=word, created_by=self.owner)
        response = self.client.get(self.url('entry', self.entry.pk))
        self.assertEqual([r['entry'].pk for r in response.context['picture_words']], [w.pk for w in words])
        self.assertContains(response, 'Words for this picture', count=1)
        self.assertNotContains(response, 'More words for this picture')
        self.assertNotContains(response, 'Words in this sentence')
        for word in words:
            self.assertContains(response, f'data-entry-id="{word.pk}"', count=1)
        self.assertNotContains(response, f'name="word_entry" value="{words[0].pk}"')
        self.assertContains(response, f'name="word_entry" value="{words[1].pk}"')
