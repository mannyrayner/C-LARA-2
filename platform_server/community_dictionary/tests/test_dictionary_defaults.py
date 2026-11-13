from django.test import TestCase
from django.urls import reverse

from community_dictionary.forms import DictionaryForm, DictionarySettingsForm
from community_dictionary.models import Dictionary
from . import test_workflow as workflow


class DictionaryDefaultsTests(TestCase):
    setUp = workflow.WorkflowTests.setUp

    def test_new_supported_languages_enable_both_ai_features(self):
        for language in ['', 'Japanese', 'French', 'Igbo', 'ig']:
            form = DictionaryForm(initial={'language': language, 'explanation_language': 'English'})
            self.assertTrue(form['image_generation_enabled'].value())
            self.assertTrue(form['sentence_capture_enabled'].value())
            self.assertIn('igbo', form.ai_languages)
        self.assertFalse(DictionaryForm(initial={'language': 'Pitjantjatjara'})['image_generation_enabled'].value())
        self.assertFalse(DictionaryForm(initial={'language': 'Pitjantjatjara'})['sentence_capture_enabled'].value())

    def test_explicit_initial_choices_and_description_dependencies_are_preserved(self):
        form = DictionaryForm(initial={'language': 'French', 'image_generation_enabled': False,
                                       'sentence_capture_enabled': False})
        self.assertFalse(form['image_generation_enabled'].value())
        self.assertFalse(form['sentence_capture_enabled'].value())
        for values in [{'tts_enabled': False}, {'explanation_language': 'unsupported'}]:
            form = DictionaryForm(initial={'language': 'French', **values})
            self.assertTrue(form['image_generation_enabled'].value())
            self.assertFalse(form['sentence_capture_enabled'].value())

    def test_submitted_opt_out_and_existing_dictionary_settings_are_not_reset(self):
        form = DictionaryForm({'name': 'Manual French', 'language': 'French'})
        self.assertTrue(form.is_valid(), form.errors)
        self.assertFalse(form.cleaned_data['image_generation_enabled'])
        self.assertFalse(form.cleaned_data['sentence_capture_enabled'])
        form = DictionarySettingsForm(instance=self.dictionary)
        self.assertFalse(form['image_generation_enabled'].value())
        self.assertFalse(form['sentence_capture_enabled'].value())

    def test_creation_page_defaults_and_submitted_features_reach_new_dictionary(self):
        self.client.force_login(self.owner)
        page = self.client.get(reverse('community_dictionary:manage'))
        self.assertTrue(page.context['form']['image_generation_enabled'].value())
        self.assertTrue(page.context['form']['sentence_capture_enabled'].value())
        self.assertContains(page, 'data-dictionary-create')
        self.assertContains(page, 'dictionary_create.js')
        self.assertNotContains(page, 'Off by default.')
        response = self.client.post(reverse('community_dictionary:manage'), {
            'name': 'New Japanese', 'language': 'Japanese', 'explanation_language': 'English',
            'tts_enabled': 'on', 'image_generation_enabled': 'on', 'sentence_capture_enabled': 'on'})
        self.assertEqual(response.status_code, 302)
        dictionary = Dictionary.objects.get(name='New Japanese')
        self.assertTrue(dictionary.image_generation_enabled)
        self.assertTrue(dictionary.sentence_capture_enabled)
