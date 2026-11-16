"""Version-bound review, native corrections, claims and automatic post-edit checks."""
import uuid
from datetime import timedelta
from unittest.mock import patch
from django.test import TestCase, override_settings, Client
from django.urls import reverse
from django.utils import timezone
from community_dictionary import capture, improve, improve_ai, refresh, text
from community_dictionary.models import Contribution, Entry, PictureCapture, Membership
from community_dictionary.services import accept, Conflict
from . import test_picture_capture as fixtures


@override_settings(OPENAI_API_KEY='test-only',CREDITS_ENABLED=False,
    PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class ImproveTests(TestCase):
    def setUp(self):
        fixtures.PictureCaptureTests.setUp(self);self.client.force_login(self.owner)
        self.entry=Entry.objects.create(dictionary=self.d,created_by=self.owner,entry_type='sentence')
        capture.component(self.entry,self.owner,'word',"Efere nri dị n'elu tebụl.",{'origin':'picture-description'})
        capture.component(self.entry,self.owner,'meaning','Plates of food are on a table.',{'origin':'picture-description'})
        self.change(word="Efere nri dị n'elu Okpokoro",meaning='A traditional family meal is served on a dining table.')
        self.result={'outcome':'suggestions','explanation':'The English describes a family meal.',
            'options':[{'basis':'meaning','sentence':"Nri ezinụlọ dị n'elu okpokoro.",
                        'translation':'A traditional family meal is served on a dining table.'}]}
        self.analyser=patch('community_dictionary.improve_ai.analyse',side_effect=lambda *a,**k:fixtures.response(self.result)).start()
        self.queue=patch('community_dictionary.improve.queue').start()
        self.refresh_queue=patch('community_dictionary.refresh.queue').start()

    def url(self,name,*args):return reverse('community_dictionary:'+name,args=[self.d.pk,*args])

    def change(self,**fields):
        for p in text.propose(self.entry,self.owner,{**fields,'edit_text':True}):accept(p,self.owner)
        self.entry.refresh_from_db()

    def start(self,**extra):
        page=self.client.get(self.url('improve-start',self.entry.pk));self.assertEqual(page.status_code,200)
        data={'permission':'on','quote':page.context['form']['quote'].value(),
              'notes':'Keep okpokoro for table.','submission_id':str(uuid.uuid4()),**extra}
        response=self.client.post(self.url('improve-start',self.entry.pk),data)
        self.assertEqual(response.status_code,302,response.content[:700])
        return PictureCapture.objects.get(pk=response.url.strip('/').split('/')[-1])

    def ready(self):
        study=self.start();improve.run(study.pk);study.refresh_from_db()
        self.assertEqual(study.status,'ready');return study

    def apply(self,study,**extra):
        option=self.result['options'][0] if self.result['options'] else {'sentence':self.entry.word,'translation':self.entry.meaning}
        return self.client.post(self.url('improve-action',study.pk),{'action':'apply','choice':0,
            'word':option['sentence'],'meaning':option['translation'],'permission':'on',
            'submission_id':str(uuid.uuid4()),**extra})

    def test_manual_control_notes_private_quote_and_no_get_calls(self):
        page=self.client.get(self.url('entry',self.entry.pk))
        self.assertContains(page,'Check and improve');self.assertNotContains(page,'Anything you would like changed?')
        page=self.client.get(self.url('improve-start',self.entry.pk))
        self.assertContains(page,'Anything you would like changed?');self.assertIn('no-store',page['Cache-Control'])
        self.client.post(self.url('improve-start',self.entry.pk),{'quote':page.context['form']['quote'].value()})
        self.assertFalse(PictureCapture.objects.exists());self.analyser.assert_not_called()

    def test_native_correction_is_supplied_and_no_wording_changes_until_approval(self):
        original=(self.entry.word,self.entry.meaning,self.entry.current_text_id,self.entry.current_meaning_id)
        study=self.ready();self.entry.refresh_from_db()
        self.assertEqual((self.entry.word,self.entry.meaning,self.entry.current_text_id,self.entry.current_meaning_id),original)
        data=self.analyser.call_args.args[0]
        self.assertIn({'rejected':'tebụl','replacement':'Okpokoro'},data['preferred_corrections']['word'])
        self.assertIn('Keep okpokoro',data['notes'])
        self.assertContains(self.client.get(self.url('improve-detail',study.pk)),'Apply suggestion and update words and audio')
        self.assertEqual(self.client.get(self.url('improve-action',study.pk)).status_code,405)
        self.assertFalse(study.speech.exists())

    def test_approval_reuses_job_and_preserves_attribution_and_history(self):
        study=self.ready();old=self.entry.current_text_id;meaning=self.entry.current_meaning_id
        response=self.apply(study);self.assertEqual(response.url,self.url('refresh-detail',study.pk))
        self.entry.refresh_from_db();study.refresh_from_db()
        self.assertEqual(self.entry.word,self.result['options'][0]['sentence'])
        self.assertEqual(self.entry.current_meaning_id,meaning)
        self.assertEqual(self.entry.current_text.previous_revision_id,old)
        self.assertTrue(Contribution.objects.filter(pk=old,status='accepted').exists())
        self.assertEqual(study.input_mode,'refresh');self.assertEqual(PictureCapture.objects.count(),1)
        self.assertIn('bilingual_check',study.usage);refresh.validate(study,payment=True)
        self.assertContains(self.client.get(self.url('entry',self.entry.pk)),'AI-assisted translation · reviewed')
        self.assertEqual(self.client.get(self.url('improve-detail',study.pk)).url,self.url('refresh-detail',study.pk))

    def test_accepted_suggestion_then_refreshes_words_and_audio(self):
        study=self.ready();self.apply(study)
        with patch('community_dictionary.port_vocabulary_ai.analyse',return_value=fixtures.response({'words':[]})):
            refresh.run(study.pk)
        study.refresh_from_db();self.assertEqual(study.status,'saved')
        self.assertTrue(study.speech.filter(entry=self.entry,status='ready').exists())
        self.assertTrue(refresh.port_vocabulary.current_state(Entry.objects.get(pk=self.entry.pk)))

    def test_reintroduced_loanword_is_not_offered(self):
        self.result['options'][0]['sentence']="Efere nri dị n'elu tebụl."
        study=self.ready();review=study.result['improve']['review']
        self.assertEqual(review['outcome'],'uncertain');self.assertEqual(review['options'],[])
        self.assertTrue(review['protected_conflict']);self.entry.refresh_from_db();self.assertIn('Okpokoro',self.entry.word)

    def test_consistent_and_uncertain_allow_keeping_text(self):
        for verdict in ('consistent','uncertain'):
            self.result.update(outcome=verdict,options=[])
            study=self.ready();page=self.client.get(self.url('improve-detail',study.pk))
            self.assertContains(page,'The descriptions already match' if verdict=='consistent' else 'Please review the intended meaning')
            response=self.client.post(self.url('improve-action',study.pk),{'action':'keep','submission_id':str(uuid.uuid4())})
            self.assertEqual(response.url,self.url('entry',self.entry.pk))
            study.refresh_from_db();self.assertEqual(study.status,'discarded')

    def test_two_meanings_offer_distinct_editable_forms(self):
        self.result['options'].append({'basis':'word','sentence':self.entry.word,'translation':'Plates of food are on a table.'})
        study=self.ready();page=self.client.get(self.url('improve-detail',study.pk))
        self.assertContains(page,'Follow the Swedish meaning');self.assertContains(page,'Follow the English meaning')
        self.assertContains(page,'id="improve-0-word"');self.assertContains(page,'id="improve-1-word"')
        self.assertEqual(self.apply(study,choice=1,word=self.entry.word,meaning='Plates of food are on a table.').status_code,302)

    def test_edit_preview_and_missing_permission(self):
        study=self.ready();self.assertEqual(self.apply(study,permission='').status_code,409)
        self.assertEqual(self.apply(study,word='My reviewed okpokoro sentence.').status_code,302)
        self.entry.refresh_from_db();self.assertEqual(self.entry.word,'My reviewed okpokoro sentence.')
        self.assertEqual(self.entry.current_text.provenance['reviewed_by'],self.owner.pk)

    def test_stale_text_refuses_publication(self):
        study=self.ready();self.change(meaning='Another human edit.')
        self.assertEqual(self.apply(study).status_code,409)
        self.entry.refresh_from_db();self.assertEqual(self.entry.meaning,'Another human edit.')
        self.assertEqual(self.client.get(self.url('improve-detail',study.pk)).status_code,409)

    def test_membership_policy_or_historical_withdrawal_refuses_apply(self):
        study=self.ready()
        previous=self.entry.current_text.previous_revision
        previous.status='withdrawn';previous.save(update_fields=['status'])
        self.assertEqual(self.apply(study).status_code,409)
        previous.status='accepted';previous.save(update_fields=['status'])
        self.d.capture_revision+=1;self.d.save(update_fields=['capture_revision'])
        self.assertEqual(self.apply(study).status_code,409)

    def test_bad_choice_cannot_apply_and_model_html_is_escaped(self):
        self.result['explanation']='</p><script>unsafe()</script>'
        study=self.ready();page=self.client.get(self.url('improve-detail',study.pk))
        self.assertContains(page,'&lt;script&gt;');self.assertNotContains(page,'<script>unsafe()')
        self.assertEqual(self.apply(study,choice=10).status_code,409)

    def test_other_editor_cannot_start_parallel_check(self):
        self.start();Membership.objects.filter(dictionary=self.d,user=self.user).update(role='co_owner')
        self.client.force_login(self.user)
        page=self.client.get(self.url('improve-start',self.entry.pk))
        response=self.client.post(self.url('improve-start',self.entry.pk),{'permission':'on',
            'quote':page.context['form']['quote'].value(),'submission_id':str(uuid.uuid4())})
        self.assertContains(response,'already running');self.assertEqual(PictureCapture.objects.count(),1)

    def test_withdrawal_during_call_prevents_publishing(self):
        study=self.start()
        def analyse(*args,**kwargs):
            self.entry.current_text.status='withdrawn';self.entry.current_text.save(update_fields=['status'])
            return fixtures.response(self.result)
        self.analyser.side_effect=analyse;improve.run(study.pk);study.refresh_from_db()
        self.assertEqual(study.status,'failed');self.assertNotIn('review',study.result['improve'])

    def test_price_change_and_expired_quote(self):
        from django.core import signing
        page=self.client.get(self.url('improve-start',self.entry.pk));token=page.context['form']['quote'].value()
        with patch('community_dictionary.photo_ai.configuration',side_effect=Conflict('prices changed')):
            response=self.client.post(self.url('improve-start',self.entry.pk),{'permission':'on','quote':token,'submission_id':str(uuid.uuid4())})
        self.assertContains(response,'prices changed');self.assertFalse(PictureCapture.objects.exists())
        with patch('django.core.signing.TimestampSigner.timestamp',return_value='1'):
            token=signing.dumps(improve.quote_values(self.owner,self.entry),salt=improve.SALT)
        response=self.client.post(self.url('improve-start',self.entry.pk),{'permission':'on','quote':token,'submission_id':str(uuid.uuid4())})
        self.assertContains(response,'estimate expired');self.assertFalse(PictureCapture.objects.exists())

    def test_duplicate_submissions_workers_and_apply(self):
        study=self.start();self.assertEqual(study.pk,self.start().pk)
        improve.run(study.pk);improve.run(study.pk);self.assertEqual(self.analyser.call_count,1)
        self.apply(study);self.apply(study)
        self.assertEqual(PictureCapture.objects.count(),1)
        self.assertEqual(Contribution.objects.filter(provenance__bilingual_check=str(study.pk)).count(),1)

    def test_network_failure_is_not_retried(self):
        study=self.start();self.analyser.side_effect=TimeoutError('private diagnostic')
        improve.run(study.pk);improve.run(study.pk);self.assertEqual(self.analyser.call_count,1)
        page=self.client.get(self.url('improve-detail',study.pk));self.assertContains(page,'Your saved wording is safe')
        self.assertNotContains(page,'private diagnostic')

    def test_unknown_processing_times_out_without_another_call(self):
        study=self.start();study.status='processing';study.result['improve']['started_at']=(timezone.now()-timedelta(minutes=16)).isoformat();study.save()
        self.client.get(self.url('improve-detail',study.pk));study.refresh_from_db()
        self.assertEqual(study.status,'failed');improve.run(study.pk);self.analyser.assert_not_called()

    def test_permissions_and_csrf(self):
        study=self.ready();self.client.force_login(self.user)
        self.assertIn(self.client.get(self.url('improve-start',self.entry.pk)).status_code,(403,404))
        Membership.objects.filter(dictionary=self.d,user=self.user).update(role='co_owner')
        self.assertEqual(self.client.get(self.url('improve-detail',study.pk)).status_code,404)
        self.client.force_login(self.outsider);self.assertEqual(self.client.get(self.url('improve-detail',study.pk)).status_code,404)
        client=Client(enforce_csrf_checks=True);client.force_login(self.owner)
        self.assertEqual(client.post(self.url('improve-action',study.pk),{'action':'apply'}).status_code,403)

    def edit(self,**extra):
        url=self.url('contribute',self.entry.pk)+'?wording=1';page=self.client.get(url)
        data={'word':self.entry.word,'meaning':self.entry.meaning,'edit_text':'1','publish_now':'on',
            'text_snapshot':page.context['form']['text_snapshot'].value(),'submission_id':str(uuid.uuid4()),
            'check_after_save':'on','check_quote':page.context['form']['check_quote'].value(),**extra}
        return self.client.post(url,data)

    def test_saved_edit_automatically_queues_check(self):
        with self.captureOnCommitCallbacks(execute=True):
            response=self.edit(meaning='An even fuller family meal description.')
        self.assertEqual(response.status_code,302,response.content[:700])
        study=PictureCapture.objects.get();self.assertEqual(response.url,self.url('improve-detail',study.pk))
        self.queue.assert_called_once_with(study.pk)
        self.entry.refresh_from_db();self.assertEqual(self.entry.meaning,'An even fuller family meal description.')
        self.analyser.assert_not_called();improve.run(study.pk);self.entry.refresh_from_db()
        self.assertEqual(self.entry.meaning,'An even fuller family meal description.')

    def test_category_only_unchanged_or_unchecked_does_not_pay(self):
        self.assertEqual(self.edit(category='Food').url,self.url('entry',self.entry.pk));self.entry.refresh_from_db()
        self.assertEqual(self.edit(meaning='Changed meaning',check_after_save='').url,self.url('refresh-start',self.entry.pk))
        self.assertFalse(PictureCapture.objects.exists());self.analyser.assert_not_called()

    def test_invalid_quote_and_exhausted_allowance_still_save(self):
        for extra in [{'check_quote':'tampered'},{}]:
            self.d.capture_daily_limit=0;self.d.save(update_fields=['capture_daily_limit'])
            response=self.edit(meaning='A saved human change',**extra);self.entry.refresh_from_db()
            self.assertEqual(self.entry.meaning,'A saved human change')
            self.assertEqual(response.url,self.url('improve-start',self.entry.pk))
            self.assertFalse(PictureCapture.objects.exists());self.change(meaning='A reset human meaning')

    def test_generic_capture_cannot_publish_advisory_result(self):
        study=self.ready()
        self.assertEqual(self.client.get(self.url('capture-detail',study.pk)).status_code,404)
        with self.assertRaises(Conflict):capture.publish(study.pk,self.owner)
        capture.prepare(study.pk);self.ai.assert_not_called()


    def test_french_and_slovak_controls_use_compiled_catalogs(self):
        for language,label in [('fr','Vérifier et améliorer'),('sk','Skontrolovať a vylepšiť')]:
            self.client.post(reverse('community_dictionary:set-language'),{'language':language})
            page=self.client.get(self.url('improve-start',self.entry.pk))
            self.assertContains(page,label)


class ParserTests(TestCase):
    def test_malformed_or_incomplete_refused(self):
        data={'preferred_corrections':{'word':[],'meaning':[]}}
        for value in [{'outcome':'consistent','explanation':'','options':[{'basis':'word','sentence':'A','translation':'B'}]},
                      {'outcome':'suggestions','explanation':'','options':[]},
                      {'outcome':'uncertain','explanation':'','options':[{'basis':'wrong','sentence':'A','translation':'B'}]}]:
            with self.subTest(value=value),self.assertRaises(ValueError):improve_ai.parse(fixtures.response(value),data)
        result=fixtures.response({'outcome':'consistent','explanation':'','options':[]});result.status='incomplete'
        with self.assertRaises(ValueError):improve_ai.parse(result,data)
