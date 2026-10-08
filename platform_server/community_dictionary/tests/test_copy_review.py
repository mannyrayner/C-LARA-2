"""Image-only copy selection and explicit editor approval during description."""
import uuid
from unittest.mock import patch
from django.test import TestCase, override_settings
from django.urls import reverse
from community_dictionary import capture, image_copy
from community_dictionary.models import Contribution, Dictionary, Entry, Membership, PictureCapture
from community_dictionary.services import Conflict
from . import test_picture_capture as base


@override_settings(OPENAI_API_KEY='test-only', CREDITS_ENABLED=False,
    PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class CopyReviewTests(TestCase):
    setUp=base.PictureCaptureTests.setUp
    url=base.PictureCaptureTests.url
    action=base.PictureCaptureTests.action
    word=base.PictureCaptureTests.word
    image=base.PictureCaptureTests.image
    publish=base.PictureCaptureTests.publish

    def pending(self):
        image=self.image(); image.status='pending'; image.save(update_fields=['status']); return image

    def copy(self, **extra):
        self.client.force_login(self.owner)
        return self.client.post(self.url('image-only-copy'),{'submission_id':uuid.uuid4(),
            'name':'Copy','permission':'on',**extra})

    def begin(self,image):
        r=self.client.post(reverse('community_dictionary:capture-image',args=[image.entry.dictionary_id,image.pk]),
            {'submission_id':uuid.uuid4(),'input_mode':'ai','input_language':'English','voice':'marin','ai_consent':'on'})
        self.assertEqual(r.status_code,302,r.content[:1000])
        return PictureCapture.objects.latest('created_at')

    def test_three_source_choices_default_both_all_copies_pending_and_source_unchanged(self):
        accepted=self.image(); pending=self.pending()
        self.client.force_login(self.owner)
        page=self.client.get(self.url('image-only-copy'))
        self.assertEqual(page.context['form']['image_status'].value(),'both')
        self.assertEqual((page.context['accepted_count'],page.context['pending_count'],page.context['image_count']),(1,1,2))
        for selection,expected in [('accepted',{accepted.pk}),('pending',{pending.pk}),('both',{accepted.pk,pending.pk})]:
            r=self.copy(image_status=selection,name=selection)
            self.assertEqual(r.status_code,302)
            self.assertTrue(r.url.endswith('?show=review'))
            target=Dictionary.objects.get(name=selection)
            images=Contribution.objects.filter(entry__dictionary=target)
            self.assertEqual(set(images.values_list('shared_from_id',flat=True)),expected)
            self.assertEqual(set(images.values_list('status',flat=True)),{'pending'})
            self.assertEqual(len(self.client.get(r.url).context['cards']),len(expected))
        accepted.refresh_from_db(); pending.refresh_from_db()
        self.assertEqual((accepted.status,pending.status),('accepted','pending'))
        self.ai.assert_not_called()

    def test_default_excludes_rejected_removed_withdrawn_archived_and_deduplicates(self):
        accepted=self.image(); pending=self.pending()
        # Same original can have a sentence derivative in a different review state.
        derivative=Contribution.objects.create(entry=accepted.entry,kind='image',status='pending',
            author=self.owner,shared_from=accepted,file_path=accepted.file_path)
        for status in ['rejected','removed','withdrawn']:
            c=self.image(); c.status=status; c.save()
        archived=self.image(); archived.entry.archived=True; archived.entry.save()
        self.copy()
        target=Dictionary.objects.get(name='Copy')
        self.assertEqual(set(Contribution.objects.filter(entry__dictionary=target).values_list('shared_from_id',flat=True)),{accepted.pk,pending.pk})
        self.assertEqual({c.pk for c in image_copy.images(self.d,'pending')},{pending.pk,derivative.pk})

    def test_invalid_selection_and_empty_subset_make_no_dictionary(self):
        self.image()
        self.assertContains(self.copy(image_status='withdrawn'),'Select a valid choice')
        self.assertContains(self.copy(image_status='pending'),'no images matching that review status')
        self.assertEqual(Dictionary.objects.count(),1)
        with self.assertRaises(Conflict): image_copy.create(self.d,self.owner,'Invalid','withdrawn')

    def test_pending_copy_preview_then_confirmation_accepts_only_copy_and_advances(self):
        original=self.pending(); second=self.image(); self.copy()
        target=Dictionary.objects.get(name='Copy')
        copied=Contribution.objects.get(entry__dictionary=target,shared_from=original)
        later=Contribution.objects.get(entry__dictionary=target,shared_from=second)
        page=self.client.get(reverse('community_dictionary:entry',args=[target.pk,copied.entry_id]))
        self.assertContains(page,'data-capture-choice')
        self.assertContains(page,'Confirming a description will also accept this picture')
        s=self.begin(copied); capture.prepare(s.pk); copied.refresh_from_db(); s.refresh_from_db()
        self.assertEqual((s.status,copied.status),('ready','pending'))
        self.assertFalse(target.entries.filter(entry_type='sentence').exists())
        review=self.client.get(reverse('community_dictionary:capture-detail',args=[target.pk,s.pk]))
        self.assertContains(review,'Saving also accepts this picture')
        sentence=capture.publish(s.pk,self.owner); capture.publish(s.pk,self.owner)
        copied.refresh_from_db(); original.refresh_from_db()
        self.assertEqual((copied.status,original.status),('accepted','pending'))
        self.assertEqual(sentence.selected_image.shared_from_id,copied.pk)
        self.assertEqual(sentence.selected_image.author_id,original.author_id)
        saved=self.client.get(reverse('community_dictionary:capture-detail',args=[target.pk,s.pk]))
        self.assertEqual(saved.context['next_image'].pk,later.pk)
        queue=self.client.get(reverse('community_dictionary:dictionary',args=[target.pk])+'?show=review')
        self.assertEqual([c['entry'].pk for c in queue.context['cards']],[later.entry_id])
        browse=self.client.get(reverse('community_dictionary:dictionary',args=[target.pk]))
        self.assertEqual([c['entry'].pk for c in browse.context['cards']],[sentence.pk])
        self.assertEqual(target.events.filter(action='accept').count(),1)

    def test_member_cannot_describe_pending_but_editor_and_coordinator_can(self):
        image=self.pending()
        self.assertNotContains(self.client.get(self.url('entry',image.entry_id)),'data-capture-choice')
        url=self.url('capture-image',image.pk)
        self.assertEqual(self.client.get(url).status_code,404)
        self.assertEqual(self.client.post(url,{'input_mode':'ai','ai_consent':'on'}).status_code,404)
        self.assertEqual(PictureCapture.objects.count(),0); self.ai.assert_not_called()
        for role in ['editor','coordinator']:
            Membership.objects.filter(dictionary=self.d,user=self.user).update(role=role)
            self.assertContains(self.client.get(self.url('entry',image.entry_id)),'data-capture-choice')
            self.assertEqual(self.client.get(url).status_code,200)
        s=self.begin(image); capture.prepare(s.pk); capture.publish(s.pk,self.user)
        image.refresh_from_db(); self.assertEqual(image.status,'accepted')

    def test_editor_role_loss_after_preview_blocks_confirmation_and_next_paid_stage(self):
        image=self.pending()
        Membership.objects.filter(dictionary=self.d,user=self.user).update(role='editor')
        s=self.begin(image); capture.prepare(s.pk)
        Membership.objects.filter(dictionary=self.d,user=self.user).update(role='contributor')
        self.assertEqual(self.action(s,'confirm',permission='yes').status_code,409)
        image.refresh_from_db(); self.assertEqual(image.status,'pending')
        self.assertFalse(Entry.objects.filter(entry_type='sentence').exists())
        s2=PictureCapture.objects.get(pk=s.pk)
        with self.assertRaises(Conflict): capture.allowed(s2,payment=True)

    def test_rejection_during_provider_call_prevents_publication(self):
        self.client.force_login(self.owner); image=self.pending(); s=self.begin(image)
        def reject(*args,**kwargs):
            Contribution.objects.filter(pk=image.pk).update(status='rejected')
            return base.response()
        self.ai.side_effect=reject; capture.prepare(s.pk); s.refresh_from_db()
        self.assertEqual(s.status,'failed')
        with self.assertRaises(Conflict): capture.publish(s.pk,self.owner)
        image.refresh_from_db(); self.assertEqual(image.status,'rejected')

    def test_discard_and_failure_leave_picture_pending(self):
        self.client.force_login(self.owner); image=self.pending(); s=self.begin(image); capture.prepare(s.pk)
        self.assertEqual(self.action(s,'discard').status_code,302)
        image.refresh_from_db(); self.assertEqual(image.status,'pending')
        self.ai.side_effect=TimeoutError(); s=self.begin(image); capture.prepare(s.pk)
        image.refresh_from_db(); self.assertEqual(image.status,'pending')
        self.assertFalse(Entry.objects.filter(entry_type='sentence').exists())

    def test_failed_publication_rolls_back_picture_approval_and_accept_event(self):
        self.client.force_login(self.owner); image=self.pending(); s=self.begin(image); capture.prepare(s.pk)
        before=self.d.events.filter(action='accept').count()
        with patch('community_dictionary.capture.write_upload',side_effect=OSError('test-only')):
            with self.assertRaises(OSError): capture.publish(s.pk,self.owner)
        image.refresh_from_db(); s.refresh_from_db()
        self.assertEqual((image.status,s.status),('pending','ready'))
        self.assertEqual(self.d.events.filter(action='accept').count(),before)
        self.assertFalse(Entry.objects.filter(entry_type='sentence').exists())

    def test_next_picture_skips_pending_for_member_includes_it_for_editor(self):
        accepted=self.image(); pending=self.pending()
        s=self.begin(accepted); capture.prepare(s.pk); capture.publish(s.pk,self.user)
        self.assertIsNone(self.client.get(self.url('capture-detail',s.pk)).context['next_image'])
        Membership.objects.filter(dictionary=self.d,user=self.user).update(role='editor')
        self.assertEqual(self.client.get(self.url('capture-detail',s.pk)).context['next_image'].pk,pending.pk)

    def test_original_pending_withdraw_restore_preserves_different_review_states(self):
        from community_dictionary.participation import withdraw_all,restore_all
        original=self.pending(); original.author=self.user; original.controlled_by=self.user; original.save()
        self.copy(); target=Dictionary.objects.get(name='Copy')
        copied=Contribution.objects.get(entry__dictionary=target,shared_from=original)
        s=self.begin(copied); capture.prepare(s.pk); sentence=capture.publish(s.pk,self.owner)
        with self.captureOnCommitCallbacks(execute=True): withdraw_all(self.user,self.d.pk,0)
        sentence.refresh_from_db(); self.assertEqual(sentence.word,'')
        restore_all(self.user,self.d.pk,1)
        original.refresh_from_db(); copied.refresh_from_db(); sentence.refresh_from_db()
        self.assertEqual((original.status,copied.status),('pending','accepted'))
        self.assertEqual(sentence.word,base.RESULT['sentence'])
