"""The third input route shares consent, review, provenance and limits."""
import uuid
from unittest.mock import patch
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings
from community_dictionary import capture_ai
from community_dictionary.capture_forms import CaptureForm
from community_dictionary.models import Entry, PictureCapture, Participation, SentenceWord
from . import test_picture_capture as base


@override_settings(OPENAI_API_KEY='test-only', CREDITS_ENABLED=False,
    PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class AIDescriptionTests(TestCase):
    setUp=base.PictureCaptureTests.setUp
    url=base.PictureCaptureTests.url
    start=base.PictureCaptureTests.start
    action=base.PictureCaptureTests.action
    ready=base.PictureCaptureTests.ready
    publish=base.PictureCaptureTests.publish
    image=base.PictureCaptureTests.image
    word=base.PictureCaptureTests.word

    def test_ai_suggestion_waits_for_confirmation_and_uses_common_publication(self):
        with patch('community_dictionary.capture_ai.transcribe') as asr:
            s=self.ready(input_mode='ai',description='')
        asr.assert_not_called()
        self.assertEqual(Entry.objects.count(),0)
        self.assertEqual(self.ai.call_args.args[1]['input_mode'],'ai')
        self.assertEqual(self.ai.call_args.args[1]['description'],'')
        self.assertContains(self.client.get(self.url('capture-detail',s.pk)),'AI-suggested description')
        e=self.publish(s)
        self.assertEqual(e.word,base.RESULT['sentence'])
        self.assertEqual(SentenceWord.objects.count(),4)
        self.assertEqual(e.current_text.provenance['input_mode'],'ai')
        self.assertEqual(e.current_text.provenance['description'],'')
        while s.speech.filter(status='waiting').exists(): self.action(s,'process')
        self.assertEqual(self.tts.call_count,5)
        self.action(s,'process'); self.publish(s)
        self.assertEqual(self.ai.call_count,1)
        self.assertEqual(self.tts.call_count,5)

    def test_unused_hidden_controls_are_ignored_before_validation(self):
        for mode in ['ai','text']:
            form=CaptureForm({'input_mode':mode,'description':'x'*1200 if mode=='ai' else 'A cat.',
                'input_language':'English','voice':'marin','ai_consent':'on'},
                {'audio':SimpleUploadedFile('bad.exe',b'not audio')},dictionary=self.d,existing=True)
            self.assertTrue(form.is_valid(),form.errors)
            self.assertFalse(form.cleaned_data.get('audio'))
            self.assertEqual(form.cleaned_data['description'],'' if mode=='ai' else 'A cat.')
        for mode,field in [('text','description'),('voice','audio'),('unknown','input_mode')]:
            form=CaptureForm({'input_mode':mode,'input_language':'English','voice':'marin','ai_consent':'on'},dictionary=self.d,existing=True)
            self.assertFalse(form.is_valid()); self.assertIn(field,form.errors)

    def test_entry_offers_three_choices_and_preserves_legacy_fallback(self):
        image=self.image(); page=self.client.get(self.url('entry',image.entry_id))
        for label in ['Type','Speak','Suggest a description','data-capture-choice']:
            self.assertContains(page,label)
        self.assertNotContains(page,'Learn from this photo')
        self.client.get(self.url('capture-image',image.pk)+'?input_mode=ai')
        self.ai.assert_not_called(); self.assertEqual(PictureCapture.objects.count(),0)
        self.d.sentence_capture_enabled=False; self.d.save()
        page=self.client.get(self.url('entry',image.entry_id))
        self.assertContains(page,'Learn from this photo'); self.assertNotContains(page,'data-capture-choice')

    def test_mode_and_feedback_language_stick_and_explicit_choice_wins(self):
        self.start(input_mode='ai',description='',input_language='Swedish')
        page=self.client.get(self.url('capture-start'))
        self.assertEqual(page.context['form']['input_mode'].value(),'ai')
        self.assertEqual(page.context['form']['input_language'].value(),'Swedish')
        page=self.client.get(self.url('capture-start')+'?input_mode=voice')
        self.assertEqual(page.context['form']['input_mode'].value(),'voice')
        self.assertTrue(page.context['choice_fixed'])
        self.client.force_login(self.owner)
        self.assertEqual(self.client.get(self.url('capture-start')).context['form']['input_mode'].value(),'text')

    def test_ai_revision_prefills_chosen_language_and_keeps_starting_preference(self):
        for language,field in [('English','translation'),('Swedish','sentence')]:
            s=self.ready(input_mode='ai',description='',input_language=language)
            revise=self.url('capture-start')+'?revise='+str(s.pk)
            page=self.client.get(revise)
            self.assertEqual(page.context['form']['description'].value(),base.RESULT[field])
            self.assertEqual(page.context['form']['input_mode'].value(),'text')
            self.assertTrue(page.context['choice_fixed'])
            r=self.client.post(revise,{'submission_id':uuid.uuid4(),'description':base.RESULT[field],
                'input_mode':'text','input_language':language,'voice':'marin','ai_consent':'on'})
            self.assertEqual(r.status_code,302)
            new=PictureCapture.objects.latest('created_at')
            self.assertEqual(new.input_mode,'text')
            self.assertTrue(new.file_path)
            self.assertEqual(self.client.session[f'capture-{self.d.pk}']['input_mode'],'ai')

    def test_ai_vocabulary_remains_editable_before_confirmation(self):
        s=self.ready(input_mode='ai',description='')
        data={'permission':'yes','words-TOTAL_FORMS':'4','words-INITIAL_FORMS':'4',
            'words-2-DELETE':'on','words-3-DELETE':'on',
            'words-0-lemma':'katt','words-0-meaning':'cat','words-0-surface':'Katten',
            'words-1-lemma':'ligga på','words-1-meaning':'lie on','words-1-surface':'ligger på'}
        r=self.action(s,'confirm',**data); self.assertEqual(r.status_code,302,r.content)
        s.refresh_from_db()
        self.assertEqual(set(Entry.objects.filter(entry_type='word').values_list('word',flat=True)),{'katt','ligga på'})
        self.assertEqual(SentenceWord.objects.count(),2)

    def test_unclear_picture_and_provider_failure_do_not_publish_or_repeat(self):
        self.ai.return_value=base.response({'outcome':'clarify','feedback':'Could you describe what matters?',
            'sentence':'','translation':'','words':[]})
        s=self.start(input_mode='ai',description=''); self.action(s,'process'); s.refresh_from_db()
        self.assertEqual(s.status,'clarify'); self.assertEqual(self.action(s,'confirm',permission='yes').status_code,409)
        self.assertEqual(self.client.get(self.url('capture-start')+'?revise='+str(s.pk)).status_code,200)
        self.ai.side_effect=TimeoutError()
        s=self.start(input_mode='ai',description=''); self.action(s,'process'); self.action(s,'process'); s.refresh_from_db()
        self.assertEqual(s.status,'failed'); self.assertEqual(self.ai.call_count,2)
        self.assertEqual(Entry.objects.count(),0)

    def test_ai_route_obeys_consent_limits_feature_switch_and_membership(self):
        data={'submission_id':uuid.uuid4(),'photo':base.picture(),'input_mode':'ai',
            'input_language':'English','voice':'marin'}
        r=self.client.post(self.url('capture-start'),data)
        self.assertEqual(r.status_code,200); self.assertIn('ai_consent',r.context['form'].errors)
        self.d.capture_daily_limit=0; self.d.save()
        data.update(photo=base.picture(),ai_consent='on')
        r=self.client.post(self.url('capture-start'),data)
        self.assertContains(r,'picture-description allowance')
        self.assertEqual(PictureCapture.objects.count(),0)
        self.d.sentence_capture_enabled=False; self.d.save()
        self.assertEqual(self.client.get(self.url('capture-start')+'?input_mode=ai').status_code,403)
        self.d.sentence_capture_enabled=True; self.d.save()
        Participation.objects.create(dictionary=self.d,user=self.user,withdrawn=True)
        self.assertEqual(self.client.get(self.url('capture-start')+'?input_mode=ai').status_code,404)
        self.client.force_login(self.outsider)
        self.assertEqual(self.client.get(self.url('capture-start')+'?input_mode=ai').status_code,404)
        csrf=Client(enforce_csrf_checks=True); csrf.force_login(self.owner)
        self.assertEqual(csrf.post(self.url('capture-start'),{'input_mode':'ai'}).status_code,403)
        self.ai.assert_not_called()

    def test_ai_adapter_uses_grounded_prompt_and_same_schema_with_mwe_guidance(self):
        # Bypass the workflow mock to exercise the actual provider adapter.
        self.ai_patch.stop()
        with patch('community_dictionary.capture_ai._openai_client') as factory:
            client=factory.return_value.__enter__.return_value
            for mode,instructions in [('ai',capture_ai.AI_INSTRUCTIONS),('text',capture_ai.INSTRUCTIONS),('voice',capture_ai.INSTRUCTIONS)]:
                capture_ai.interpret(base.picture().read(),{'input_mode':mode,'target_language':'Swedish'},model='test',api_key='test')
                request=client.responses.create.call_args.kwargs
                self.assertTrue(request['instructions'].startswith(instructions))
                self.assertIn('sträcka ut sig',request['instructions'])
                self.assertEqual(request['text']['format']['schema'],capture_ai.SCHEMA)
                self.assertFalse(request['store'])
            self.assertEqual(factory.call_args.kwargs['max_retries'],0)
