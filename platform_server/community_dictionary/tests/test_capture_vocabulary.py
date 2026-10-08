"""Correction workflow and image-copy custody, with no live provider calls."""
import copy
import uuid
from unittest.mock import patch
from django.test import TestCase, Client, override_settings
from django.urls import reverse
from community_dictionary import capture, capture_ai, capture_vocabulary
from community_dictionary.models import (Entry, Contribution, Dictionary, PictureCapture,
    CaptureSpeech, Membership, SentenceWord, Participation)
from community_dictionary.storage import path_for
from . import test_picture_capture as base


@override_settings(OPENAI_API_KEY='test-only', CREDITS_ENABLED=False,
    PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class CaptureVocabularyTests(TestCase):
    setUp=base.PictureCaptureTests.setUp
    url=base.PictureCaptureTests.url
    start=base.PictureCaptureTests.start
    ready=base.PictureCaptureTests.ready
    action=base.PictureCaptureTests.action
    word=base.PictureCaptureTests.word
    image=base.PictureCaptureTests.image
    publish=base.PictureCaptureTests.publish

    def form_data(self, words):
        data={'words-TOTAL_FORMS':len(words),'words-INITIAL_FORMS':len(words),
              'words-MIN_NUM_FORMS':0,'words-MAX_NUM_FORMS':12,'permission':'yes'}
        for i,word in enumerate(words):
            for key,value in word.items(): data[f'words-{i}-{key}']=value
        return data

    def test_shared_mwe_rules_and_examples_are_language_specific(self):
        sv=capture_vocabulary.mwe_guidance('Swedish')
        self.assertIn('reflexiva',sv)
        self.assertIn('Tillbaka på hotellet',sv)
        self.assertIn('sträcka ut sig',sv)
        self.assertIn('zieht … an',capture_vocabulary.mwe_guidance('German'))
        self.assertIn('lexicalized',capture_vocabulary.mwe_guidance('unknown-language'))

    def test_contiguous_and_separated_mwe_forms_parse(self):
        for sentence,surface,lemma in [
            ('Katten sträcker ut sig på soffan.','sträcker ut sig','sträcka ut sig'),
            ('Katten sträcker långsamt ut sig.','sträcker … ut sig','sträcka ut sig'),
            ('Der Mann zieht seine Jacke an.','zieht … an','anziehen')]:
            result=copy.deepcopy(base.RESULT);result['sentence']=sentence
            result['words']=[{'surface':surface,'lemma':lemma,'meaning':'example','existing_id':0}]
            self.assertEqual(capture_ai.parse(base.response(result))['words'][0]['lemma'],lemma)
        for bad in ['an … zieht','zieht … missing','ann','… an','zieht … zieht']:
            self.assertFalse(capture_vocabulary.aligned_surface(bad,'Der Mann zieht seine Jacke an.'))
        self.assertFalse(capture_vocabulary.aligned_surface('soff','Katten ligger på soffan.'))

    def test_edit_remove_add_and_whole_expression_audio(self):
        result=copy.deepcopy(base.RESULT)
        result['sentence']='Katten sträcker ut sig på soffan.'
        result['words']=[{'surface':'sträcker','lemma':'sträcka','meaning':'stretch','existing_id':0},
                        {'surface':'ut','lemma':'ut','meaning':'out','existing_id':0}]
        self.ai.return_value=base.response(result)
        s=self.ready()
        rows=[{'lemma':'sträcka ut sig','surface':'sträcker ut sig','meaning':'stretch out'},
              {'lemma':'ut','surface':'ut','meaning':'out','DELETE':'on'},
              {'lemma':'soffa','surface':'soffan','meaning':'sofa'},
              {'lemma':'bekväm','surface':'','meaning':'comfortable'}]
        data=self.form_data(rows)
        r=self.action(s,'confirm',**data);self.assertEqual(r.status_code,302,r.content[:1000])
        s.refresh_from_db()
        self.assertEqual(s.result['suggested_words'],result['words'])
        self.assertEqual(s.result['vocabulary_edited_by'],self.user.pk)
        self.assertFalse(self.d.entries.filter(word__in=['sträcka','ut']).exists())
        phrase=self.d.entries.get(word='sträcka ut sig')
        self.assertEqual(SentenceWord.objects.get(word_entry=phrase).surface,'sträcker ut sig')
        self.assertEqual(phrase.current_text.provenance['confirmed_words'][0]['lemma'],'sträcka ut sig')
        capture.run_audio(str(s.pk))
        self.assertIn('sträcka ut sig',[c.args[0] for c in self.tts.call_args_list])
        self.assertEqual(self.ai.call_count,1)
        self.action(s,'confirm',**data)
        self.assertEqual(self.d.entries.filter(entry_type='sentence').count(),1)

    def test_invalid_edits_show_errors_and_preserve_input_without_publishing(self):
        s=self.ready()
        for rows,message in [
            ([{'lemma':'katt','meaning':'','surface':'Katten'}],'This field is required'),
            ([{'lemma':'katt','meaning':'cat','surface':'dog'}],'Copy the form from the sentence'),
            ([{'lemma':'katt','meaning':'cat'},{'lemma':'KATT','meaning':'cat'}],'appear twice')]:
            r=self.action(s,'confirm',**self.form_data(rows))
            self.assertContains(r,message)
            self.assertContains(r,'value="katt"')
            s.refresh_from_db();self.assertEqual(s.status,'ready')
        self.assertEqual(Entry.objects.count(),0)
        r=self.action(s,'confirm',permission='yes',**{'words-TOTAL_FORMS':'broken'})
        self.assertContains(r,'ManagementForm')
        self.assertEqual(Entry.objects.count(),0)

    def test_all_suggestions_can_be_deleted(self):
        s=self.ready()
        rows=[{**w,'DELETE':'on'} for w in s.result['words']]
        self.assertEqual(self.action(s,'confirm',**self.form_data(rows)).status_code,302)
        self.assertEqual(self.d.entries.count(),1)
        self.assertFalse(SentenceWord.objects.exists())
        self.assertEqual(CaptureSpeech.objects.count(),1)

    def test_maximum_and_audio_worker_handle_twelve_words(self):
        s=self.ready()
        rows=[{'lemma':f'ord {i}','meaning':f'word {i}','surface':''} for i in range(13)]
        self.assertContains(self.action(s,'confirm',**self.form_data(rows)),'at most 12')
        self.assertFalse(Entry.objects.exists())
        r=self.action(s,'confirm',**self.form_data(rows[:12]));self.assertEqual(r.status_code,302)
        capture.run_audio(str(s.pk))
        self.assertEqual(self.tts.call_count,13)
        self.assertFalse(CaptureSpeech.objects.filter(status='waiting').exists())

    def test_no_javascript_add_preserves_edits(self):
        s=self.ready()
        r=self.action(s,'add-word',**self.form_data([{'lemma':'edited','meaning':'meaning','surface':''}]))
        self.assertContains(r,'value="edited"')
        self.assertContains(r,'name="words-1-lemma"')
        self.assertFalse(Entry.objects.exists())

    def test_reuse_is_by_sense_in_this_dictionary_not_submitted_ids(self):
        old=self.word()
        other=Dictionary.objects.create(owner=self.outsider,name='Other',language='Swedish')
        foreign=Entry.objects.create(dictionary=other,created_by=self.outsider,word='katt',meaning='cat')
        s=self.ready()
        self.action(s,'confirm',**self.form_data([{'lemma':'katt','meaning':'cat','surface':'Katten','existing_id':foreign.pk}]))
        self.assertEqual(SentenceWord.objects.get().word_entry_id,old.pk)
        self.assertEqual(old.current_text.author,self.owner)

    def copy_images(self,**extra):
        self.client.force_login(self.owner)
        return self.client.post(self.url('image-only-copy'),{'submission_id':uuid.uuid4(),
            'name':'Image test copy','permission':'on',**extra})

    def test_image_copy_contains_only_images_and_preserves_custody(self):
        original=self.image()
        # A derived sentence owns a physical image copy of the same original.
        self.client.post(self.url('capture-image',original.pk),{'submission_id':uuid.uuid4(),
            'description':'The cat is lying on the sofa.','input_language':'English',
            'input_mode':'text','voice':'marin','ai_consent':'on'})
        s=PictureCapture.objects.get();self.action(s,'process');self.publish(s)
        before=self.d.entries.count()
        result=self.copy_images();self.assertEqual(result.status_code,302,result.content[:1000])
        target=Dictionary.objects.get(name='Image test copy')
        self.assertEqual(target.entries.count(),1)
        entry=target.entries.get();image=entry.contributions.get()
        self.assertEqual((entry.word,entry.meaning,entry.category),('','',''))
        self.assertEqual(image.kind,'image');self.assertEqual(image.status,'pending')
        self.assertEqual(image.shared_from_id,original.pk)
        self.assertEqual(image.author_id,original.author_id)
        self.assertEqual(image.controlled_by_id,original.author_id)
        self.assertEqual(image.file_path,original.file_path)
        self.assertTrue(path_for(image.file_path).exists())
        self.assertEqual((target.language,target.explanation_language),('Swedish','English'))
        self.assertTrue(target.sentence_capture_enabled)
        self.assertFalse(target.image_generation_enabled)
        self.assertFalse(target.memberships.exists())
        self.assertEqual(self.d.entries.count(),before)
        self.assertEqual(self.ai.call_count,1) # only the preceding capture
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(result.url).status_code,404)

    def test_copy_post_replay_is_idempotent_and_get_read_only(self):
        self.image();self.client.force_login(self.owner)
        self.assertContains(self.client.get(self.url('settings')),'Create an image-only copy')
        self.assertContains(self.client.get(self.url('image-only-copy')),'Both: 1 distinct picture')
        self.assertEqual(Dictionary.objects.count(),1)
        token=uuid.uuid4()
        a=self.copy_images(submission_id=token);b=self.copy_images(submission_id=token)
        self.assertEqual(a.url,b.url);self.assertEqual(Dictionary.objects.count(),2)
        self.assertEqual(self.ai.call_count,0)

    def test_copy_permissions_and_csrf(self):
        self.image()
        for user in [self.user,self.outsider]:
            self.client.force_login(user)
            self.assertEqual(self.client.get(self.url('image-only-copy')).status_code,404)
            self.assertEqual(self.client.post(self.url('image-only-copy'),{'name':'copy','permission':'on'}).status_code,404)
        self.client.force_login(self.owner)
        self.assertContains(self.copy_images(permission=''),'This field is required')
        strict=Client(enforce_csrf_checks=True);strict.force_login(self.owner)
        self.assertEqual(strict.post(self.url('image-only-copy'),{'name':'copy'}).status_code,403)
        self.assertEqual(Dictionary.objects.count(),1)

    def test_copy_includes_pending_and_excludes_archived_images(self):
        accepted=self.image();pending=self.image();archived=self.image()
        pending.status='pending';pending.save()
        archived.entry.archived=True;archived.entry.save()
        self.copy_images()
        target=Dictionary.objects.get(name='Image test copy')
        self.assertEqual(set(Contribution.objects.filter(entry__dictionary=target).values_list('shared_from_id',flat=True)),{accepted.pk,pending.pk})

    def test_missing_image_rolls_back_entire_copy(self):
        first=self.image();second=self.image();path_for(second.file_path).unlink()
        result=self.copy_images();self.assertContains(result,'An image file is missing')
        self.assertEqual(Dictionary.objects.count(),1)
        self.assertTrue(path_for(first.file_path).exists())

    def test_withdraw_restore_follows_images_into_test_copy_and_derived_sentences(self):
        from community_dictionary.participation import withdraw_all,restore_all
        original=self.image()
        original.refresh_from_db();original.author=self.user;original.controlled_by=self.user;original.save()
        r=self.copy_images();self.assertEqual(r.status_code,302,r.content.decode())
        target=Dictionary.objects.get(name='Image test copy');image=target.entries.get().selected_image
        # Owner of copy creates a sentence dependent on another contributor's photo.
        self.client.post(reverse('community_dictionary:capture-image',args=[target.pk,image.pk]),
            {'submission_id':uuid.uuid4(),'description':'cat','input_language':'English','input_mode':'text','voice':'marin','ai_consent':'on'})
        study=PictureCapture.objects.get();capture.prepare(study.pk);sentence=capture.publish(study.pk,self.owner)
        with self.captureOnCommitCallbacks(execute=True): withdraw_all(self.user,self.d.pk,0)
        image.refresh_from_db();sentence.refresh_from_db()
        self.assertNotEqual(image.entry.dictionary_id,target.pk)
        self.assertEqual(sentence.word,'')
        self.assertFalse(capture.sentence_links(target).exists())
        restore_all(self.user,self.d.pk,1)
        image.refresh_from_db();sentence.refresh_from_db()
        self.assertEqual(image.entry.dictionary_id,target.pk)
        self.assertEqual(sentence.word,base.RESULT['sentence'])
        self.assertEqual(capture.sentence_links(target).count(),4)
