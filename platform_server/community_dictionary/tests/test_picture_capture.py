import copy
import io
import json
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace
import tempfile
import uuid
from unittest.mock import patch
import wave
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase, override_settings, Client
from django.urls import reverse
from django.utils import timezone
from community_dictionary import capture, capture_ai
from community_dictionary.models import (Dictionary, Membership, Entry, Contribution, PictureCapture,
    CaptureSpeech, SentenceWord, AttentionReport, Participation, LanguageCheck)
from community_dictionary.services import add_contributions
from community_dictionary.storage import path_for
from community_dictionary.tests.test_workflow import picture
from projects.models import AIUsageCharge

RESULT={'outcome':'ready','feedback':'The cat is lying on the sofa. Is that what you mean?',
    'sentence':'Katten ligger på soffan.','translation':'The cat is lying on the sofa.',
    'words':[{'surface':'Katten','lemma':'katt','meaning':'cat','existing_id':0},
             {'surface':'ligger','lemma':'ligga','meaning':'lie','existing_id':0},
             {'surface':'på','lemma':'på','meaning':'on','existing_id':0},
             {'surface':'soffan','lemma':'soffa','meaning':'sofa','existing_id':0}]}

def response(data=None):
    return SimpleNamespace(status='completed',output_text=json.dumps(data or RESULT),
        usage=SimpleNamespace(input_tokens=1000,output_tokens=300))

def speech(*args,report=None,**kwargs):
    report.update(speech_cost_usd='0.001',guidance_cost_usd='0',attempts=[{'outcome':'usable'}])
    out=io.BytesIO()
    with wave.open(out,'wb') as wav:
        wav.setnchannels(1);wav.setsampwidth(2);wav.setframerate(24000);wav.writeframes(b'\x00\x10'*2400)
    return (out.getvalue(),'audio/wav','.wav'),.1

@override_settings(OPENAI_API_KEY='test-only',CREDITS_ENABLED=False,
    PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class PictureCaptureTests(TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup)
        config=override_settings(COMMUNITY_DICTIONARY_MEDIA_ROOT=Path(temp.name)/'private',MEDIA_ROOT=Path(temp.name)/'public')
        config.enable();self.addCleanup(config.disable)
        User=get_user_model()
        self.owner=User.objects.create_user('capture-owner',password='test')
        self.user=User.objects.create_user('capture-member',password='test')
        self.outsider=User.objects.create_user('capture-outsider',password='test')
        self.d=Dictionary.objects.create(owner=self.owner,name='Swedish',language='Swedish',explanation_language='English',sentence_capture_enabled=True)
        Membership.objects.create(dictionary=self.d,user=self.user,accepted=True)
        self.client.force_login(self.user)
        self.ai_patch=patch('community_dictionary.capture_ai.interpret',return_value=response())
        self.ai=self.ai_patch.start()
        self.tts=patch('community_dictionary.tts.synthesize',side_effect=speech).start()
        self.addCleanup(patch.stopall)
    def url(self,name,*args):
        return reverse('community_dictionary:'+name,args=[self.d.pk,*args])
    def start(self,**extra):
        r=self.client.post(self.url('capture-start'),{'submission_id':uuid.uuid4(),'photo':picture(),
            'description':'The cat is lying on the sofa.','input_language':'English','input_mode':'text',
            'voice':'marin','ai_consent':'on',**extra})
        self.assertEqual(r.status_code,302,r.content[:1000])
        return PictureCapture.objects.latest('created_at')
    def action(self,s,action,**extra):
        return self.client.post(self.url('capture-action',s.pk),{'action':action,**extra})
    def ready(self,**extra):
        s=self.start(**extra);r=self.action(s,'process');self.assertEqual(r.status_code,302);s.refresh_from_db();self.assertEqual(s.status,'ready');return s
    def publish(self,s):
        r=self.action(s,'confirm',permission='yes');self.assertEqual(r.status_code,302,r.content[:1000]);s.refresh_from_db();return s.saved_entry
    def word(self,word='katt',meaning='cat'):
        e=Entry.objects.create(dictionary=self.d,created_by=self.owner)
        add_contributions(e,self.owner,{'word':word,'meaning':meaning},[],publish=True);e.refresh_from_db();return e
    def image(self):
        e=self.word('soffa','sofa')
        from community_dictionary.storage import prepare_upload
        c=add_contributions(e,self.owner,{'prepared_photo':prepare_upload(picture(),'image')},[],publish=True)[0]
        return c
    def test_confirmation_publishes_for_member_and_receipts_prevent_duplicates(self):
        s=self.start();self.assertEqual(self.ai.call_count,0)
        self.client.get(self.url('capture-detail',s.pk));self.assertEqual(self.ai.call_count,0)
        self.assertEqual(self.action(s,'confirm',permission='yes').status_code,409)
        self.action(s,'process');self.action(s,'process');self.assertEqual(self.ai.call_count,1)
        self.assertEqual(self.action(s,'confirm').status_code,409)
        entry=self.publish(s);self.publish(s)
        self.assertEqual(Entry.objects.filter(entry_type='sentence').count(),1)
        self.assertEqual(Entry.objects.count(),5)
        self.assertEqual(entry.word,RESULT['sentence'])
        self.assertEqual(SentenceWord.objects.count(),4)
        self.assertFalse(Contribution.objects.filter(status='pending').exists())
        self.assertEqual(CaptureSpeech.objects.count(),5)
        self.assertContains(self.client.get(self.url('dictionary')+'?view=sentences'),RESULT['sentence'])
        self.assertNotContains(self.client.get(self.url('dictionary')+'?view=words'),RESULT['sentence'])
    def test_post_retry_does_not_create_another_attempt(self):
        token=uuid.uuid4();self.start(submission_id=token);self.start(submission_id=token)
        self.assertEqual(PictureCapture.objects.count(),1)
    def test_senses_reuse_without_overwriting_existing_contributions_or_audio(self):
        old=self.word();old_text=old.current_text_id
        Contribution.objects.create(entry=old,author=self.owner,kind='audio',status='accepted',file_path='fake.wav')
        other_sense=self.word('ligga','be located')
        s=self.ready();entry=self.publish(s)
        old.refresh_from_db();self.assertEqual(old.current_text_id,old_text)
        self.assertEqual(Entry.objects.filter(word='katt').count(),1)
        self.assertEqual(Entry.objects.filter(word='ligga').count(),2)
        self.assertFalse(s.speech.filter(entry=old).exists())
        self.assertContains(self.client.get(self.url('word',old.pk)),entry.word)
        self.assertNotContains(self.client.get(self.url('word',other_sense.pk)),entry.word)
    def test_speech_is_saved_once_and_obeys_current_text_identity(self):
        s=self.ready();entry=self.publish(s)
        while s.speech.filter(status='waiting').exists(): self.action(s,'process')
        self.assertEqual(self.tts.call_count,5)
        self.assertEqual(Contribution.objects.filter(kind='audio').count(),5)
        self.action(s,'process');self.assertEqual(self.tts.call_count,5)
        self.assertContains(self.client.get(self.url('entry',entry.pk)),'AI-generated voice')
        add_contributions(entry,self.owner,{'word':'Katten sover.','edit_text':True},[],publish=True)
        entry.refresh_from_db()
        self.assertEqual(capture.sentence_context(entry)['sentence_words'],[])
        self.assertEqual(self.client.get(self.url('capture-detail',s.pk)).url,self.url('entry',entry.pk))
        from community_dictionary.lexicon import recordings
        self.assertEqual(recordings(entry,self.d),[])
    def test_edit_during_generation_discards_audio(self):
        s=self.ready();entry=self.publish(s);clip=s.speech.get(entry=entry)
        def changed(*args,**kw):
            add_contributions(entry,self.owner,{'word':'Changed sentence','edit_text':True},[],publish=True)
            return speech(*args,**kw)
        self.tts.side_effect=changed
        capture.speak(clip.pk);clip.refresh_from_db();self.assertEqual(clip.status,'failed')
        self.assertFalse(entry.contributions.filter(kind='audio').exists())
    def test_voice_input_and_feedback_use_input_language(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        wav,_=speech(report={})
        asr=SimpleNamespace(text='The cat is lying on the sofa.',usage=SimpleNamespace(type='tokens',input_tokens=120,output_tokens=12))
        with patch('community_dictionary.capture_ai.transcribe',return_value=asr) as mock:
            s=self.ready(input_mode='voice',audio=SimpleUploadedFile('voice.wav',wav[0],content_type='audio/wav'))
        self.assertEqual(mock.call_args.args[1],'en')
        self.assertEqual(s.description,asr.text)
        self.action(s,'process');self.assertEqual(self.tts.call_args.kwargs['language'],'en')
        feedback=self.client.get(self.url('capture-media',s.pk,'feedback'));self.assertEqual(feedback.status_code,200);feedback.close()
    def test_invalid_or_unaligned_model_output_does_not_publish(self):
        result=copy.deepcopy(RESULT);result['words'][0]['surface']='not present'
        self.ai.return_value=response(result)
        s=self.start();self.action(s,'process');s.refresh_from_db();self.assertEqual(s.status,'failed')
        self.assertEqual(self.action(s,'confirm',permission='yes').status_code,409)
    def test_clarification_retains_picture_and_description_for_revision(self):
        self.ai.return_value=response({'outcome':'clarify','feedback':'Which animal do you mean?', 'sentence':'','translation':'','words':[]})
        s=self.start();self.action(s,'process');s.refresh_from_db();self.assertEqual(s.status,'clarify')
        self.assertEqual(self.action(s,'confirm',permission='yes').status_code,409)
        page=self.client.get(self.url('capture-start')+'?revise='+str(s.pk))
        self.assertContains(page,'The cat is lying on the sofa.')
    def test_existing_picture_and_next_picture_and_original_links(self):
        image=self.image();next_image=self.image()
        r=self.client.post(self.url('capture-image',image.pk),{'submission_id':uuid.uuid4(),'description':'The cat is lying on the sofa.',
            'input_language':'English','input_mode':'text','voice':'marin','ai_consent':'on'})
        self.assertEqual(r.status_code,302)
        s=PictureCapture.objects.get();self.action(s,'process');entry=self.publish(s)
        self.assertEqual(entry.selected_image.shared_from_id,image.pk)
        self.assertEqual(entry.selected_image.controlled_by_id,self.owner.pk)
        page=self.client.get(self.url('capture-detail',s.pk));self.assertContains(page,self.url('capture-image',next_image.pk))
        self.assertContains(self.client.get(self.url('entry',image.entry_id)),entry.word)
        self.assertContains(self.client.get(self.url('entry',entry.pk)),'Original picture and discussion')
        # Published source links remain the navigation evidence after draft expiry.
        s.delete()
        self.assertTrue(Contribution.objects.filter(shared_from=image,entry=entry,status='accepted').exists())
        self.client.post(self.url('capture-image',next_image.pk),{'submission_id':uuid.uuid4(),
            'description':'The cat is lying on the sofa.','input_language':'English','input_mode':'text',
            'voice':'marin','ai_consent':'on'})
        second=PictureCapture.objects.get();self.action(second,'process');self.publish(second)
        self.assertIsNone(self.client.get(self.url('capture-detail',second.pk)).context['next_image'])
    def test_withdrawal_removes_derived_sentence_and_words_and_private_preview(self):
        image=self.image()
        self.client.post(self.url('capture-image',image.pk),{'submission_id':uuid.uuid4(),'description':'The cat is lying on the sofa.',
            'input_language':'English','input_mode':'text','voice':'marin','ai_consent':'on'})
        s=PictureCapture.objects.get();self.action(s,'process');entry=self.publish(s)
        private_path=s.file_path
        from community_dictionary.collections import withdraw
        with self.captureOnCommitCallbacks(execute=True): withdraw(self.owner,[image.pk])
        entry.refresh_from_db();self.assertEqual(entry.word,'')
        self.assertFalse(path_for(private_path).exists())
        s.refresh_from_db();self.assertEqual(s.status,'discarded')
        self.assertEqual(self.client.get(self.url('capture-media',s.pk,'picture')).status_code,404)
        self.assertFalse(capture.sentence_links(self.d).exists())
    def test_withdraw_during_provider_call_does_not_resurrect_result(self):
        s=self.start()
        def revoke(*args,**kwargs):
            Participation.objects.create(dictionary=self.d,user=self.user,withdrawn=True,revision=1)
            return response()
        self.ai.side_effect=revoke
        self.action(s,'process');s.refresh_from_db();self.assertEqual(s.status,'failed');self.assertEqual(s.result,{})
        self.assertEqual(self.client.get(self.url('capture-detail',s.pk)).status_code,404)
    def test_settings_disable_invalidates_saved_and_unsaved_previews(self):
        s=self.ready();self.client.force_login(self.owner)
        response_=self.client.post(self.url('settings'),{'name':'Swedish','language':'Swedish','explanation_language':'English',
            'text_direction':'auto','photo_ai_enabled':'on','tts_enabled':'on'})
        self.assertEqual(response_.status_code,302);s.refresh_from_db();self.assertEqual(s.status,'discarded')
    def test_outsiders_and_other_members_cannot_read_or_process_private_attempts(self):
        s=self.ready()
        for user in [self.owner,self.outsider]:
            self.client.force_login(user)
            self.assertEqual(self.client.get(self.url('capture-detail',s.pk)).status_code,404)
            self.assertEqual(self.client.get(self.url('capture-media',s.pk,'picture')).status_code,404)
            self.assertEqual(self.action(s,'process').status_code,404)
    def test_attention_is_shared_and_language_check_requires_editor_current_revision(self):
        s=self.ready();entry=self.publish(s)
        r=self.client.post(self.url('flag',entry.pk),{'submission_id':uuid.uuid4(),'reason':'Please check the verb'})
        self.assertEqual(r.status_code,302)
        self.assertContains(self.client.get(self.url('attention')),'Please check the verb')
        data={'text_id':entry.current_text_id,'meaning_id':entry.current_meaning_id}
        self.assertEqual(self.client.post(self.url('language-checked',entry.pk),data).status_code,404)
        self.client.force_login(self.owner)
        self.assertEqual(self.client.post(self.url('language-checked',entry.pk),{**data,'text_id':0}).status_code,409)
        self.assertEqual(self.client.post(self.url('language-checked',entry.pk),data).status_code,302)
        self.assertIsNotNone(AttentionReport.objects.get().resolved_at)
        self.assertTrue(capture.sentence_context(entry)['language_check'])
        add_contributions(entry,self.owner,{'meaning':'A changed meaning','edit_text':True},[],publish=True);entry.refresh_from_db()
        self.assertFalse(capture.sentence_context(entry)['language_check'])
    def test_expiry_removes_private_assets_but_keeps_published_content(self):
        s=self.ready();entry=self.publish(s)
        PictureCapture.objects.filter(pk=s.pk).update(expires_at=timezone.now()-timedelta(seconds=1))
        path=s.file_path
        with self.captureOnCommitCallbacks(execute=True): call_command('expire_photo_studies',stdout=io.StringIO())
        self.assertFalse(path_for(path).exists());self.assertTrue(path_for(entry.selected_image.file_path).exists())
        self.assertTrue(Entry.objects.filter(pk=entry.pk).exists())
    def test_csrf_and_get_requests_cannot_publish(self):
        s=self.ready()
        self.assertEqual(self.client.get(self.url('capture-action',s.pk)).status_code,405)
        client=Client(enforce_csrf_checks=True);client.force_login(self.user)
        self.assertEqual(client.post(self.url('capture-action',s.pk),{'action':'confirm','permission':'yes'}).status_code,403)
    def test_failed_provider_does_not_retry_and_usage_is_recorded_once(self):
        self.ai.side_effect=TimeoutError('private content must not be logged')
        s=self.start();self.action(s,'process');self.action(s,'process');self.assertEqual(self.ai.call_count,1)
        self.ai.side_effect=None;s=self.ready();self.action(s,'process')
        self.assertEqual(AIUsageCharge.objects.filter(request_type=f'capture:{s.pk}:interpretation').count(),1)
    def test_quota_and_low_balance_prevent_new_provider_attempts(self):
        with override_settings(COMMUNITY_DICTIONARY_CAPTURE_DAILY_LIMIT=0):
            r=self.client.post(self.url('capture-start'),{'submission_id':uuid.uuid4(),'photo':picture(),'description':'cat',
                'input_language':'English','input_mode':'text','voice':'marin','ai_consent':'on'})
            self.assertContains(r,'picture-description allowance')
        self.assertEqual(PictureCapture.objects.count(),0)
        with patch('community_dictionary.capture_views.has_minimum_balance_for_compile',return_value=False):
            r=self.client.post(self.url('capture-start'),{'submission_id':uuid.uuid4(),'photo':picture(),'description':'cat',
                'input_language':'English','input_mode':'text','voice':'marin','ai_consent':'on'})
            self.assertContains(r,'balance is too low')
        self.assertEqual(self.ai.call_count,0)

    def test_background_worker_redelivery_does_not_duplicate_audio(self):
        s=self.ready();entry=self.publish(s)
        capture.run_audio(str(s.pk));capture.run_audio(str(s.pk))
        self.assertEqual(self.tts.call_count,5)
        self.assertEqual(entry.contributions.filter(kind='audio').count(),1)
        self.assertFalse(s.speech.filter(status='waiting').exists())

    def test_revision_hides_generated_picture_links_as_well_as_sentence_links(self):
        from community_dictionary.lexicon import valid_links
        s=self.ready();entry=self.publish(s)
        self.assertEqual(valid_links(self.d).filter(image=entry.selected_image).count(),4)
        add_contributions(entry,self.owner,{'word':'Katten sover.','edit_text':True},[],publish=True)
        self.assertEqual(valid_links(self.d).filter(image=entry.selected_image).count(),0)

    def test_withdraw_restore_preserves_sentence_identity_and_link_revision_checks(self):
        from community_dictionary.participation import withdraw_all, restore_all
        from community_dictionary.lexicon import valid_links
        s=self.ready();entry=self.publish(s)
        capture.run_audio(str(s.pk))
        original_text=entry.current_text_id;original_count=Contribution.objects.count()
        with self.captureOnCommitCallbacks(execute=True): withdraw_all(self.user,self.d.pk,0)
        entry.refresh_from_db();self.assertEqual(entry.word,'')
        self.assertFalse(valid_links(self.d).exists())
        restore_all(self.user,self.d.pk,1)
        entry.refresh_from_db();self.assertEqual(entry.current_text_id,original_text)
        self.assertEqual(Contribution.objects.count(),original_count)
        self.assertEqual(capture.sentence_links(self.d).count(),4)
        self.assertEqual(valid_links(self.d).count(),4)
        add_contributions(entry,self.owner,{'word':'Katten sover.','edit_text':True},[],publish=True)
        self.assertEqual(valid_links(self.d).count(),0)

    def test_export_contains_sentence_links_but_no_private_capture_records(self):
        import zipfile
        s=self.ready();self.publish(s)
        self.client.force_login(self.owner)
        output=self.client.get(self.url('export'))
        with zipfile.ZipFile(io.BytesIO(b''.join(output.streaming_content))) as z:
            records=json.loads(z.read('records.json'))
            names=[row['model'] for row in records]
            self.assertIn('community_dictionary.sentenceword',names)
            self.assertNotIn('community_dictionary.picturecapture',names)
            self.assertNotIn('community_dictionary.capturespeech',names)
        output.close()

    def test_spoofed_existing_id_cannot_link_a_different_dictionary(self):
        other=Dictionary.objects.create(owner=self.outsider,name='Other',language='Swedish')
        foreign=Entry.objects.create(dictionary=other,created_by=self.outsider,word='katt',meaning='cat')
        data=copy.deepcopy(RESULT);data['words'][0]['existing_id']=foreign.pk
        self.ai.return_value=response(data)
        s=self.ready();entry=self.publish(s)
        self.assertFalse(SentenceWord.objects.filter(sentence_text=entry.current_text,word_entry=foreign).exists())

    def test_api_adapters_use_image_schema_language_hint_and_no_sdk_retry(self):
        self.ai_patch.stop()
        from unittest.mock import MagicMock
        client=MagicMock();client.responses.create.return_value=response()
        manager=MagicMock();manager.__enter__.return_value=client
        with patch('community_dictionary.capture_ai._openai_client',return_value=manager) as factory:
            photo=picture().read()
            result=capture_ai.interpret(photo,{'description':'The cat'},model='gpt-6-sol',api_key='fake')
            self.assertEqual(capture_ai.parse(result)['sentence'],RESULT['sentence'])
            sent=client.responses.create.call_args.kwargs
            self.assertFalse(sent['store']);self.assertTrue(sent['text']['format']['strict'])
            self.assertEqual(sent['input'][0]['content'][1]['type'],'input_image')
            self.assertEqual(factory.call_args.kwargs['max_retries'],0)
            # Adapter streams files through a closed context manager (Windows-safe).
            import tempfile
            with tempfile.TemporaryDirectory() as temp:
                path=Path(temp)/'description.wav';path.write_bytes(speech(report={})[0][0])
                capture_ai.transcribe(path,'sv','fake')
                self.assertEqual(client.audio.transcriptions.create.call_args.kwargs['language'],'sv')
                self.assertTrue(client.audio.transcriptions.create.call_args.kwargs['file'].closed)
