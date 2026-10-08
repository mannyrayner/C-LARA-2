"""A manual replacement must become usable in its originating example."""
import copy
import uuid
from django.test import TestCase, override_settings
from community_dictionary import capture
from community_dictionary.models import AudioStudy, Contribution
from . import test_picture_capture as base


@override_settings(OPENAI_API_KEY='test-only', CREDITS_ENABLED=False,
    PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class AudioRecoveryTests(TestCase):
    setUp=base.PictureCaptureTests.setUp
    url=base.PictureCaptureTests.url
    start=base.PictureCaptureTests.start
    ready=base.PictureCaptureTests.ready
    action=base.PictureCaptureTests.action
    publish=base.PictureCaptureTests.publish

    def failed_example(self):
        result=copy.deepcopy(base.RESULT)
        result['sentence']='Katten sitter i bakgrunden.'
        result['words']=[{'surface':'i bakgrunden','lemma':'i bakgrunden','meaning':'in the background','existing_id':0}]
        self.ai.return_value=base.response(result)
        study=self.ready(); sentence=self.publish(study)
        word=self.d.entries.get(word='i bakgrunden')
        clip=study.speech.get(entry=word)
        self.tts.side_effect=TimeoutError('provider-detail')
        capture.speak(clip.pk)
        self.tts.side_effect=base.speech
        return study,sentence,word,clip

    def replacement(self,word,*,publish=True):
        r=self.client.post(self.url('audio-start',word.pk),{'submission_id':uuid.uuid4(),
            'source_text_id':word.current_text_id,'source_text_version':word.text_version,
            'ai_consent':'on','voice':'marin'})
        self.assertEqual(r.status_code,302)
        audio=AudioStudy.objects.latest('created_at')
        data={'action':'save','consent':'on'}
        if publish: data['publish_now']='on'
        self.assertEqual(self.client.post(self.url('audio-action',audio.pk),data).status_code,302)
        audio.refresh_from_db()
        return audio.saved_contribution

    def test_saved_replacement_plays_from_both_views_and_clears_old_warning(self):
        study,sentence,word,clip=self.failed_example()
        self.assertContains(self.client.get(self.url('capture-detail',study.pk)), 'Audio could not be created')
        self.client.force_login(self.owner)
        audio=self.replacement(word)
        self.client.force_login(self.user)
        preview=self.client.get(self.url('capture-detail',study.pk))
        self.assertEqual(preview.context['word_rows'][0]['audio'].pk,audio.pk)
        self.assertContains(preview,self.url('media',audio.pk))
        self.assertNotContains(preview,'Audio could not be created')
        entry=self.client.get(self.url('entry',sentence.pk))
        self.assertContains(entry,self.url('media',audio.pk))
        clip.refresh_from_db()
        self.assertEqual(clip.status,'failed')  # Historical attempt/cost is not rewritten.
        self.assertEqual(clip.report['failure_code'],'timeout')
        self.assertEqual(self.tts.call_count,2)  # Original attempt plus the explicit replacement.

    def test_private_preview_alone_does_not_resolve_failure(self):
        study,sentence,word,clip=self.failed_example()
        self.client.post(self.url('audio-start',word.pk),{'submission_id':uuid.uuid4(),
            'source_text_id':word.current_text_id,'source_text_version':word.text_version,
            'ai_consent':'on','voice':'marin'})
        page=self.client.get(self.url('capture-detail',study.pk))
        self.assertIsNone(page.context['word_rows'][0]['audio'])
        self.assertContains(page,'Audio could not be created')

    def test_pending_replacement_does_not_bypass_review(self):
        study,sentence,word,clip=self.failed_example()
        audio=self.replacement(word)
        self.assertEqual(audio.status,'pending')
        page=self.client.get(self.url('capture-detail',study.pk))
        self.assertIsNone(page.context['word_rows'][0]['audio'])
        self.assertContains(page,'Audio could not be created')
        self.assertNotContains(page,self.url('media',audio.pk))

    def test_withdrawn_or_outdated_audio_does_not_resolve_failure(self):
        study,sentence,word,clip=self.failed_example()
        self.client.force_login(self.owner);audio=self.replacement(word)
        self.client.force_login(self.user)
        Contribution.objects.filter(pk=audio.pk).update(status='withdrawn')
        self.assertContains(self.client.get(self.url('capture-detail',study.pk)),'Audio could not be created')
        audio.status='accepted';audio.provenance['source_text']='different words';audio.save()
        page=self.client.get(self.url('capture-detail',study.pk))
        self.assertIsNone(page.context['word_rows'][0]['audio'])
        self.assertContains(page,'Audio could not be created')
