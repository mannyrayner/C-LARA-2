"""Bulk pictures and costs remain scoped, recoverable and honest across retries."""
from datetime import timedelta
from decimal import Decimal
import json
from unittest.mock import patch
import uuid

from django.db import transaction
from django.test import TestCase, override_settings
from django.utils import timezone

from . import test_lemma_images as fixtures
from community_dictionary import lemma_images as pictures, lemma_picture_costs as costs
from community_dictionary.models import Contribution, Dictionary, Entry, ImageStudy, LemmaImage, Membership
from projects.models import AIUsageCharge


@override_settings(**fixtures.LemmaImageTests._overridden_settings)
class WordPictureOverviewTests(TestCase):
    setUp = fixtures.LemmaImageTests.setUp
    url = fixtures.LemmaImageTests.url
    word = fixtures.LemmaImageTests.word
    response = fixtures.LemmaImageTests.response
    run_job = fixtures.LemmaImageTests.run_job
    attempt = fixtures.LemmaImageTests.attempt
    post_picture = fixtures.LemmaImageTests.post_picture

    def selection(self, words, **data):
        page=self.client.get(self.url('word-images'),{'shown':100})
        tokens={c['entry'].pk:c['token'] for c in page.context['cards']}
        return {'selection':[tokens[w.pk] for w in words], 'submission_id':str(uuid.uuid4()), **data}

    def preview(self, words):
        return self.client.post(self.url('word-images'),self.selection(words,action='preview'))

    def generate(self, words, **changes):
        page=self.preview(words)
        return self.client.post(self.url('word-images'),{'action':'generate','quote':page.context['quote'],
            'ai_consent':'on','submission_id':str(uuid.uuid4()),**changes},follow=True)

    def test_grid_thumbnails_statuses_and_more_words_are_read_only(self):
        ready=self.attempt();self.run_job(ready)
        abstract=self.attempt(self.word('eftersom','because'));self.run_job(abstract,'none')
        blocked=self.attempt(self.word('hund','dog'))
        blocked.status='failed';blocked.analysis={'error':'Daily image limit reached.'};blocked.save()
        for n in range(24):self.word('word'+str(n),'meaning')
        charges=AIUsageCharge.objects.count()
        page=self.client.get(self.url('word-images'))
        self.assertEqual(len(page.context['cards']),20)
        self.assertContains(page,self.url('media',ready.image_id))
        for label in ['No simple picture','Resource limit reached','Not yet attempted','Show more words','Select all shown']:
            self.assertContains(page,label)
        self.assertEqual(len(self.client.get(self.url('word-images'),{'shown':40}).context['cards']),27)
        self.assertEqual(AIUsageCharge.objects.count(),charges)
        self.assertEqual(ImageStudy.objects.count(),2)

    def test_selected_generation_regenerates_existing_and_unattempted_words_with_durable_totals(self):
        old=self.attempt();self.run_job(old);old_image=old.image_id
        fresh=self.word('hund','dog')
        preview=self.preview([old.entry,fresh])
        self.assertEqual([e.pk for e in preview.context['candidates']],[old.entry_id,fresh.pk])
        self.assertContains(preview,'Estimated batch cost')
        self.assertEqual(ImageStudy.objects.count(),1)
        data={'action':'generate','quote':preview.context['quote'],'ai_consent':'on','submission_id':str(uuid.uuid4())}
        started=self.client.post(self.url('word-images'),data,follow=True)
        batch_id=started.context['batch']['id']
        self.assertEqual(started.context['batch']['pending'],2)
        self.assertEqual(pictures.daily_usage(self.d,self.owner)['account_used'],1)
        self.assertEqual(self.client.post(self.url('word-images'),data).status_code,302)
        self.assertEqual(ImageStudy.objects.count(),3)
        old.refresh_from_db();self.assertEqual(pictures.picture(old.entry)['id'],old_image)
        self.run_job(old)
        second=LemmaImage.objects.get(entry=fresh);self.run_job(second,'none')
        result=self.client.get(self.url('word-images'),{'batch':batch_id})
        self.assertTrue(result.context['batch']['complete'])
        self.assertContains(result,'Actual batch cost')
        self.assertEqual(result.context['batch']['unknown'],0)
        self.assertEqual(Decimal(result.context['batch']['exact_amount']),Decimal('.031750'))
        self.assertEqual(Decimal(result.context['cumulative']['exact_amount']),Decimal('.062875'))
        self.assertEqual(self.client.get(self.url('word-images')).context['batch']['id'],batch_id)
        self.assertContains(result,'Recent batches')

    @override_settings(COMMUNITY_DICTIONARY_IMAGE_DAILY_LIMIT=1)
    def test_unstarted_receipts_do_not_spend_or_block_the_allowance(self):
        words=[self.word(),self.word('hund','dog')]
        started=self.generate(words,extra_allowance='on')
        self.assertEqual(started.status_code,200)
        self.assertEqual(started.context['batch']['pending'],2)
        self.assertEqual(pictures.daily_usage(self.d,self.owner)['remaining'],1)
        self.assertEqual(ImageStudy.objects.count(),2)
        for word in words:
            row=LemmaImage.objects.get(entry=word);self.run_job(row)
            self.assertEqual(row.status,'ready')
        self.assertEqual(pictures.daily_usage(self.d,self.owner)['account_used'],2)
        self.assertEqual(costs.batch_summary(self.d,self.owner)['unknown'],0)

    @override_settings(COMMUNITY_DICTIONARY_IMAGE_DAILY_LIMIT=2)
    def test_resource_skips_have_zero_batch_cost_without_provider_calls(self):
        words=[self.word(),self.word('hund','dog')];self.generate(words)
        for _ in range(2):
            ImageStudy.objects.create(dictionary=self.d,user=self.owner,kind='style',
                expires_at=timezone.now()+timedelta(days=1),model='fixture',status='saved')
        with patch.object(pictures,'analyse') as analysis:
            for row in LemmaImage.objects.all():pictures.run(row.pk,row.revision)
        analysis.assert_not_called()
        summary=costs.batch_summary(self.d,self.owner)
        self.assertEqual(summary['skipped'],2)
        self.assertEqual(summary['unknown'],0)
        self.assertEqual(Decimal(summary['exact_amount']),0)
        self.assertTrue(summary['complete'])
        self.assertFalse(AIUsageCharge.objects.exists())

    def test_unknown_usage_and_charged_failures_are_not_reported_as_free(self):
        word=self.word();self.generate([word]);row=LemmaImage.objects.get(entry=word)
        with patch.object(pictures,'analyse',side_effect=TimeoutError):pictures.run(row.pk,row.revision)
        summary=costs.batch_summary(self.d,self.owner)
        self.assertEqual(summary['unknown'],1);self.assertEqual(summary['amount'],'0.00')
        self.assertContains(self.client.get(self.url('word-images')),'Partial total')
        self.generate([word]);row.refresh_from_db()
        self.run_job(row,generate=(None,{'prompt_tokens':100,'completion_tokens':200},'provider_or_image_error'))
        later=costs.batch_summary(self.d,self.owner)
        self.assertEqual(later['unknown'],0)
        self.assertEqual(Decimal(later['exact_amount']),Decimal('.007125'))
        self.assertEqual(costs.cumulative(self.d)['unknown'],1)
        first=ImageStudy.objects.order_by('created_at').first()
        self.assertEqual(costs.batch_summary(self.d,self.owner,first.usage[costs.KEY]['batch'])['unknown'],1)

    def test_remove_and_undo_keep_words_contributions_and_costs(self):
        row=self.attempt();self.run_job(row);empty=self.word('hund','dog')
        before=costs.cumulative(self.d)
        removed=self.client.post(self.url('word-images'),self.selection([row.entry,empty],action='remove'),follow=True)
        self.assertContains(removed,'Undo picture removal')
        token=removed.context['undo']
        self.assertEqual(LemmaImage.objects.filter(status='removed').count(),2)
        self.assertEqual(Entry.objects.count(),2)
        self.assertEqual(Contribution.objects.filter(kind='image',status='accepted').count(),1)
        self.assertEqual(costs.cumulative(self.d),before)
        restored=self.client.post(self.url('word-images'),{'action':'undo','undo':token,'submission_id':str(uuid.uuid4())},follow=True)
        self.assertContains(restored,'Pictures restored: 2')
        row.refresh_from_db();self.assertEqual(row.status,'ready')
        self.assertFalse(LemmaImage.objects.filter(entry=empty).exists())
        self.assertEqual(costs.cumulative(self.d),before)

    def test_removal_and_undo_do_not_overwrite_new_choices_or_withdrawn_images(self):
        row=self.attempt();self.run_job(row)
        stale=self.selection([row.entry],action='remove')
        self.post_picture(row.entry,action='illustration')
        denied=self.client.post(self.url('word-images'),stale)
        self.assertContains(denied,'Refresh before removing')
        row.refresh_from_db();self.assertEqual(row.suitability,'illustration')
        removed=self.client.post(self.url('word-images'),self.selection([row.entry],action='remove'),follow=True)
        image=Contribution.objects.get(pk=row.image_id);image.status='withdrawn';image.save()
        undone=self.client.post(self.url('word-images'),{'action':'undo','undo':removed.context['undo'],'submission_id':str(uuid.uuid4())},follow=True)
        self.assertContains(undone,'Pictures restored: 0')
        row.refresh_from_db();self.assertEqual(row.status,'removed')

    def test_superseded_unstarted_batch_settles_without_replaying_or_erasing_history(self):
        word=self.word();first=self.generate([word]);row=LemmaImage.objects.get(entry=word);old_revision=row.revision
        old_batch=first.context['batch']['id']
        removed=self.client.post(self.url('word-images'),self.selection([word],action='remove'),follow=True)
        self.assertTrue(costs.batch_summary(self.d,self.owner,old_batch)['complete'])
        with patch.object(pictures,'analyse') as analysis:pictures.run(row.pk,old_revision)
        analysis.assert_not_called()
        self.assertEqual(costs.batch_summary(self.d,self.owner,old_batch)['amount'],'0.00')
        self.assertEqual(ImageStudy.objects.count(),1)
        self.assertFalse(AIUsageCharge.objects.exists())

    def test_selection_limit_tampering_and_cross_dictionary_tokens_are_rejected(self):
        word=self.word();valid=self.selection([word],action='preview')
        invalid={**valid,'selection':[valid['selection'][0]+'tamper']}
        self.assertContains(self.client.post(self.url('word-images'),invalid),'selection expired')
        self.assertContains(self.client.post(self.url('word-images'),{**valid,'selection':valid['selection']*51}),'between 1 and 50')
        other=Dictionary.objects.create(owner=self.owner,name='Other',language='Swedish')
        old_pk=self.d.pk;self.d.pk=other.pk
        self.assertContains(self.client.post(self.url('word-images'),valid),'selection expired')
        self.d.pk=old_pk
        self.assertFalse(ImageStudy.objects.exists())
        self.assertFalse(AIUsageCharge.objects.exists())

    def test_costs_include_personal_keys_and_history_after_regeneration_and_archival(self):
        word=self.word();self.generate([word]);row=LemmaImage.objects.get(entry=word)
        with patch.object(pictures.photo_ai,'api_credentials',return_value=('fixture',True)), patch.object(pictures.images,'api_credentials',return_value=('fixture',True)):
            # Fresh quotes are required when payment changes.
            row.quote=pictures.quote(self.owner,self.d);row.save()
            ImageStudy.objects.filter(pk=row.study_id).update(personal_key=True)
            self.run_job(row)
        self.assertFalse(AIUsageCharge.objects.exists())
        self.assertEqual(Decimal(costs.cumulative(self.d)['exact_amount']),Decimal('.031125'))
        word.archived=True;word.save()
        self.assertEqual(Decimal(costs.cumulative(self.d)['exact_amount']),Decimal('.031125'))
        legacy=ImageStudy.objects.create(dictionary=self.d,user=self.owner,entry=word,kind='entry',
            expires_at=timezone.now()+timedelta(days=1),model='fixture',personal_key=True,status='failed',accounted=True)
        self.assertEqual(costs.cumulative(self.d)['unknown'],1)
        from community_dictionary.capture import charge
        discarded=ImageStudy.objects.create(dictionary=self.d,user=self.owner,entry=word,kind='entry',
            expires_at=timezone.now()+timedelta(days=1),model='fixture',status='discarded')
        charge(discarded,'lemma_picture_plan',Decimal('.000625'),'fixture','lemma_picture_plan')
        self.assertEqual(costs.cumulative(self.d)['unknown'],2)

    def test_another_requester_cannot_open_a_private_batch_and_other_dictionary_costs_are_excluded(self):
        word=self.word();started=self.generate([word]);row=LemmaImage.objects.get(entry=word);self.run_job(row)
        own_total=costs.cumulative(self.d)['exact_amount']
        membership=Membership.objects.get(dictionary=self.d,user=self.member);membership.role='editor';membership.save()
        self.client.force_login(self.member)
        page=self.client.get(self.url('word-images'),{'batch':started.context['batch']['id']})
        self.assertIsNone(page.context['batch'])
        self.assertEqual(page.context['cumulative']['exact_amount'],own_total)
        other=Dictionary.objects.create(owner=self.owner,name='Other',language='Swedish')
        other_word=Entry.objects.create(dictionary=other,created_by=self.owner,word='other')
        ImageStudy.objects.create(dictionary=other,user=self.owner,entry=other_word,kind='entry',
            expires_at=timezone.now()+timedelta(days=1),model='fixture',cost_usd=Decimal('100'),accounted=True,status='saved')
        self.assertEqual(costs.cumulative(self.d)['exact_amount'],own_total)

    def test_client_selection_and_scroll_regressions(self):
        import shutil, subprocess
        from pathlib import Path
        node=shutil.which('node')
        if not node:self.skipTest('Node is unavailable for the isolated client-state tests.')
        result=subprocess.run([node,'--test',str(Path(__file__).with_name('word_images_state.test.cjs'))],capture_output=True,text=True,timeout=15)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)

    def test_translated_overview_and_cost_labels(self):
        from django.urls import reverse
        self.word()
        for language,label in [('fr','Coût cumulé'),('sk','Celková cena')]:
            self.client.post(reverse('community_dictionary:set-language'),{'language':language})
            page=self.client.get(self.url('word-images'))
            self.assertContains(page,label)
            self.assertContains(page,'data-picture-id')

    def test_removing_during_planning_keeps_returned_cost_and_prevents_image_call(self):
        word=self.word();started=self.generate([word]);row=LemmaImage.objects.get(entry=word)
        def remove_while_planning(*args):
            self.client.post(self.url('word-images'),self.selection([word],action='remove'))
            return self.response()
        with patch.object(pictures,'analyse',side_effect=remove_while_planning),patch.object(pictures.images,'generate') as image:
            pictures.run(row.pk,row.revision)
        image.assert_not_called()
        row.refresh_from_db();self.assertEqual(row.status,'removed')
        batch=costs.batch_summary(self.d,self.owner,started.context['batch']['id'])
        self.assertTrue(batch['complete']);self.assertEqual(batch['unknown'],0)
        self.assertEqual(Decimal(batch['exact_amount']),Decimal('.000625'))

    def test_known_provider_cost_survives_local_billing_failure(self):
        word=self.word();self.generate([word]);row=LemmaImage.objects.get(entry=word)
        with patch.object(pictures,'analyse',return_value=self.response()),patch('community_dictionary.capture.charge',side_effect=RuntimeError),patch.object(pictures.images,'generate') as image:
            pictures.run(row.pk,row.revision)
        image.assert_not_called()
        batch=costs.batch_summary(self.d,self.owner)
        self.assertEqual(batch['unknown'],0)
        self.assertEqual(Decimal(batch['exact_amount']),Decimal('.000625'))

    def test_pending_bulk_does_not_block_a_guided_image_request(self):
        from types import SimpleNamespace
        from community_dictionary.guided_words import admit_image
        words=[self.word(),self.word('hund','dog')];self.generate(words)
        capture=SimpleNamespace(user=self.owner,dictionary=self.d,membership_revision=0,participation_revision=0,expires_at=timezone.now()+timedelta(days=1),
            result={'guided':{'words':{'text':'A bird','style_description':'simple'}}})
        study=admit_image(capture)
        self.assertEqual(study.status,'processing')
        self.assertEqual(pictures.daily_usage(self.d,self.owner)['account_used'],1)
        self.assertEqual(costs.batch_summary(self.d,self.owner)['pending'],2)

    def test_private_thumbnails_are_small_and_follow_media_withdrawal_permissions(self):
        import io
        from PIL import Image
        word=self.word();row=self.attempt(word)
        buffer=io.BytesIO();Image.new('RGBA',(600,400),'blue').save(buffer,'PNG')
        self.run_job(row,generate=((buffer.getvalue(),'image/png','.png'),{'prompt_tokens':1,'completion_tokens':1},''))
        thumbnail=self.client.get(self.url('media',row.image_id),{'thumbnail':1})
        self.assertEqual(thumbnail.status_code,200)
        self.assertEqual(thumbnail['Content-Type'],'image/jpeg')
        self.assertEqual(thumbnail['Cache-Control'],'private, no-store')
        with Image.open(io.BytesIO(thumbnail.content)) as image:self.assertEqual(max(image.size),256)
        self.client.force_login(self.outsider)
        self.assertEqual(self.client.get(self.url('media',row.image_id),{'thumbnail':1}).status_code,404)
        self.client.force_login(self.owner)
        image=row.image;image.status='withdrawn';image.save()
        self.assertEqual(self.client.get(self.url('media',row.image_id),{'thumbnail':1}).status_code,404)

    def test_explicit_retry_of_interrupted_old_attempt_retains_unknown_cost(self):
        word=self.word();started=self.generate([word]);row=LemmaImage.objects.get(entry=word)
        costs.track(row.study,started=True,status='analysing',planning_started=True)
        row.status='analysing';row.updated_at=timezone.now()-timedelta(minutes=11);row.save()
        self.generate([word]);row.refresh_from_db();self.run_job(row)
        self.assertEqual(row.status,'ready')
        old=costs.batch_summary(self.d,self.owner,started.context['batch']['id'])
        self.assertTrue(old['complete']);self.assertEqual(old['unknown'],1)
        self.assertEqual(costs.cumulative(self.d)['unknown'],1)
