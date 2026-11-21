"""Picture rotation is private, stable on reload and separate from practice results."""
from datetime import timedelta
from unittest.mock import patch
from django.test import TestCase, override_settings
from django.utils import timezone
from community_dictionary import practice_history as history, learning, picture_practice as practice
from community_dictionary.models import Contribution, ContributionPreference, PictureCapture
from . import test_picture_practice as base


@override_settings(OPENAI_API_KEY='test-only', CREDITS_ENABLED=False,
    PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class PictureHistoryTests(TestCase):
    setUp = base.PicturePracticeTests.setUp
    url = base.PicturePracticeTests.url
    word = base.PicturePracticeTests.word
    image = base.PicturePracticeTests.image

    def shown(self, **query):
        page = self.client.get(self.url('picture-practice'), query, follow=True)
        self.assertEqual(page.status_code, 200)
        return page.context['image']

    def state(self):
        return ContributionPreference.objects.get(user=self.user, dictionary=self.d).consent[history.KEY]

    def attempt(self, picture, *, user=None, days=0, mode='voice', status='feedback', outcome='ready'):
        return PictureCapture.objects.create(dictionary=self.d, user=user or self.user,
            source_image=picture, input_mode='practice', language=self.d.language,
            created_at=timezone.now()-timedelta(days=days), expires_at=timezone.now()+timedelta(days=1),
            status=status, result={'practice':{'mode':mode,'feedback':{'outcome':outcome}}})

    def test_rotation_avoids_recent_five_and_mixes_new_with_old(self):
        for _ in range(11): self.image()
        seen = []
        with patch.object(history.random, 'choice', side_effect=lambda items:items[0]):
            for _ in range(15):
                selected = self.shown()
                key = history.identity(selected.file_path)
                self.assertNotIn(key, seen[-5:])
                seen.append(key)
        # Six initial pictures establish a review pool; then two new, one review.
        self.assertEqual(len(set(seen[:6])), 6)
        self.assertIn(seen[6], seen[:6])
        self.assertNotIn(seen[7], seen[:7]); self.assertNotIn(seen[8], seen[:8])
        self.assertIn(seen[9], seen[:9])
        self.assertEqual(PictureCapture.objects.count(), 0)
        self.review.assert_not_called(); self.asr.assert_not_called(); self.tts.assert_not_called()

    def test_reloading_pinned_picture_and_try_again_do_not_inflate_history(self):
        shown = self.shown()
        before = self.state()
        self.shown(image=shown.pk); self.shown(image=shown.pk)
        self.assertEqual(self.state(), before)
        self.client.logout(); self.client.force_login(self.user)
        self.shown(image=shown.pk)
        self.assertEqual(self.state(), before)

    def test_two_picture_dictionary_alternates_and_shared_file_copies_are_one_picture(self):
        other = self.image()
        Contribution.objects.create(entry=self.photo.entry, kind='image', status='accepted',
            author=self.user, file_path=self.photo.file_path)
        pictures = [self.shown() for _ in range(5)]
        self.assertEqual(len(self.state()['seen']), 2)
        self.assertTrue(all(a.file_path != b.file_path for a,b in zip(pictures,pictures[1:])))
        self.assertEqual({x.file_path for x in pictures}, {self.photo.file_path, other.file_path})

    def test_history_is_seeded_from_own_attempts_and_isolated_between_members(self):
        other = self.image()
        self.attempt(self.photo)
        self.assertEqual(self.shown().pk, other.pk)
        self.assertIn(history.identity(self.photo.file_path), self.state()['seen'])
        self.client.force_login(self.owner)
        with patch.object(history.random, 'choice', side_effect=lambda items:items[0]):
            self.assertEqual(self.shown().pk, self.photo.pk)
        own = ContributionPreference.objects.get(user=self.owner, dictionary=self.d).consent[history.KEY]
        self.assertNotIn(history.identity(other.file_path), own['seen'])

    def test_switching_workflows_and_practice_options_preserves_history_not_consent(self):
        self.shown()
        before = self.state()
        from django.test import RequestFactory
        request = RequestFactory().get('/')
        request.user = self.user; request.session = {}
        learning.save_preference(request, self.d, 'manual')
        learning.save_guided_choices(request, self.d, {'start_with':'picture'})
        from django.db import transaction
        with transaction.atomic(): practice.save_choices(self.user, self.d, {'mode':'text'})
        self.assertEqual(self.state(), before)
        self.assertNotIn(history.KEY, learning.preference(request, self.d)['consent'])

    def test_withdrawn_or_wrong_category_pictures_are_never_selected(self):
        other = self.image()
        self.photo.status = 'withdrawn'; self.photo.save(update_fields=['status'])
        self.assertEqual(self.shown().pk, other.pk)
        missing = self.client.get(self.url('picture-practice'), {'category':'not available'}, follow=True)
        self.assertEqual(missing.status_code, 200)
        self.assertIsNone(missing.context['image'])
        self.assertEqual(self.client.get(self.url('picture-practice'), {'image':self.photo.pk}).status_code, 404)

    def test_overview_counts_completed_activity_not_recognition_or_other_learners(self):
        self.attempt(self.photo)
        self.attempt(self.photo, mode='text')
        self.attempt(self.photo, days=2)
        self.attempt(self.photo, status='transcript')
        self.attempt(self.photo, status='feedback', outcome='clarify')
        self.attempt(self.photo, status='failed')
        self.attempt(self.photo, status='discarded')
        self.attempt(self.photo, days=31)
        self.attempt(self.photo, user=self.owner)
        self.shown(image=self.photo.pk)
        counts = history.overview(self.user, self.d)
        self.assertEqual(counts, {'completed':3, 'spoken':2, 'active_days':2, 'pictures':1})
        page = self.client.get(self.url('picture-practice'), {'image':self.photo.pk})
        self.assertContains(page, 'My practice')
        self.assertContains(page, 'Completed attempts: 3')
        self.assertContains(page, 'not a language proficiency score')
