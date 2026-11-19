from decimal import Decimal
from types import SimpleNamespace
from django.test import SimpleTestCase, TestCase, override_settings
from community_dictionary.practice_costs import summary
from . import test_picture_practice as base


class Clips:
    def __init__(self, *clips): self.clips = clips
    def filter(self, **kwargs): return self
    def order_by(self, *args): return self.clips


def attempt(mode='voice', *, confirmed=False, parent=None, usage=None, clips=()):
    return SimpleNamespace(result={'practice': {'mode': mode, 'confirmed': confirmed, 'parent_attempt': parent}},
        usage=usage or {}, speech=Clips(*clips), personal_key=False)


class PracticeCostTests(SimpleTestCase):
    def test_all_components_include_confirmation_and_optional_speech(self):
        study=attempt(confirmed=True,usage={'practice_transcription':{'cost_usd':'.0005'},
            'practice_feedback':{'cost_usd':'.011'}, 'practice_feedback_confirmed':{'cost_usd':'.005'}},
            clips=[SimpleNamespace(status='ready',report={'speech_cost_usd':'.002','guidance_cost_usd':'0'})])
        data=summary(study)
        self.assertEqual(data['known_total'],Decimal('.0185'))
        self.assertTrue(data['complete'])
        self.assertEqual([x['stage'] for x in data['items']],['recognition','review','confirmation','speech'])

    def test_unknown_usage_and_uncertain_audio_are_not_reported_as_a_complete_zero(self):
        data=summary(attempt(usage={'practice_feedback':{'cost_usd':'.011'}},
            clips=[SimpleNamespace(status='failed',report={'speech_cost_usd':'0','uncertain_cost':True})]))
        self.assertFalse(data['complete'])
        self.assertEqual(data['known_total'],Decimal('.011'))
        self.assertIsNone(data['items'][0]['cost'])
        self.assertFalse(summary(attempt())['has_known'])

    def test_revision_does_not_double_count_earlier_transcription_or_review(self):
        data=summary(attempt(confirmed=True,parent='previous',usage={
            'practice_feedback_confirmed':{'cost_usd':'.005'}}))
        self.assertTrue(data['complete'])
        self.assertEqual(data['known_total'],Decimal('.005'))
        self.assertEqual([x['stage'] for x in data['items']],['confirmation'])
        typed=summary(attempt('text',usage={'practice_feedback':{'cost_usd':'0'}}))
        self.assertTrue(typed['has_known'])
        self.assertTrue(typed['complete'])
        self.assertEqual(typed['known_total'],Decimal('0'))


@override_settings(OPENAI_API_KEY='test-only', CREDITS_ENABLED=False,
    PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class PracticeCostPageTests(TestCase):
    url=base.PicturePracticeTests.url
    word=base.PicturePracticeTests.word
    image=base.PicturePracticeTests.image
    start=base.PicturePracticeTests.start
    attempt=base.PicturePracticeTests.attempt
    act=base.PicturePracticeTests.act
    feedback=base.PicturePracticeTests.feedback
    def setUp(self): base.PicturePracticeTests.setUp(self)

    def test_generation_is_explicit_extra_and_page_and_export_include_existing_feedback_cost(self):
        study=self.feedback()
        page=self.client.get(self.url('picture-practice-detail',study.pk))
        self.assertContains(page,'Generate spoken version')
        self.assertContains(page,'+~US$')
        self.assertContains(page,'Estimated cost so far:')
        self.assertContains(page,'AI image review and language feedback')
        self.assertContains(page,'Unknown usage is not counted as zero.')
        self.tts.assert_not_called()
        rows=self.client.get(self.url('picture-practice-log')).json()['attempts']
        self.assertEqual(rows[0]['cost_summary']['known_total'],str(study.usage['practice_feedback']['cost_usd']))
        self.assertEqual(self.review.call_count,1)
