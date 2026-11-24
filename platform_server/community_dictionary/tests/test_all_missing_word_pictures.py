"""One approval covers the frozen dictionary-wide missing-picture set."""
from datetime import timedelta
import uuid

from django.test import TestCase, override_settings
from django.utils import timezone

from . import test_lemma_images as fixtures
from . import test_word_picture_overview as overview_fixtures
from community_dictionary import lemma_images as pictures, lemma_picture_costs as costs
from community_dictionary.models import ImageStudy, LemmaImage, Membership


@override_settings(**fixtures.LemmaImageTests._overridden_settings)
class AllMissingWordPicturesTests(TestCase):
    setUp = fixtures.LemmaImageTests.setUp
    url = fixtures.LemmaImageTests.url
    word = fixtures.LemmaImageTests.word
    attempt = fixtures.LemmaImageTests.attempt
    response = fixtures.LemmaImageTests.response
    run_job = fixtures.LemmaImageTests.run_job
    selection = overview_fixtures.WordPictureOverviewTests.selection

    def preview(self, **changes):
        return self.client.post(self.url('word-images'), {'action':'preview_missing', **changes})

    def confirmation(self, preview, **changes):
        return {'action':'generate_missing', 'quote':preview.context['quote'],
            'ai_consent':'on', 'submission_id':str(uuid.uuid4()), **changes}

    def removed(self):
        word=self.word('removed','removed')
        LemmaImage.objects.create(entry=word,requested_by=self.owner,status='removed',
            suitability='none',snapshot=pictures.basis(word))
        return word

    def test_preview_covers_dictionary_and_skips_existing_deliberate_and_active_pictures(self):
        ready=self.attempt();self.run_job(ready)
        none=self.attempt(self.word('abstract','because'));self.run_job(none,'none')
        none.snapshot={};none.save()
        waiting=self.attempt(self.word('waiting','waiting'))
        old=self.attempt(self.word('uncertain','uncertain'))
        old.status='generating';old.updated_at=timezone.now()-timedelta(hours=1);old.save()
        self.removed()
        uploaded=self.attempt(self.word('uploaded','uploaded'));self.run_job(uploaded);uploaded.delete()
        failed=self.attempt(self.word('retry','retry'));failed.status='failed'
        failed.analysis={'error':'Daily image limit reached.'};failed.save()
        words=[self.word('fresh'+str(i),'fresh') for i in range(61)]
        withdrawn=self.word('withdrawn','withdrawn')
        part=withdrawn.current_text;part.status='withdrawn';part.save()
        sentence=self.word('sentence','sentence');sentence.entry_type='sentence';sentence.save()
        before=ImageStudy.objects.count()
        page=self.preview(q='does not match',shown=20,page=99)
        self.assertEqual({w.pk for w in page.context['candidates']},{failed.entry_id,*[w.pk for w in words]})
        self.assertTrue(page.context['all_missing'])
        self.assertTrue(page.context['allowance_needed'])
        self.assertEqual(page.context['manual_selected_count'],0)
        self.assertEqual(page.context['selection_data'],{})
        self.assertFalse(page.context['server_selection'])
        self.assertContains(page,'Missing pictures across the whole dictionary: 62')
        self.assertContains(page,'one-off allowance')
        self.assertEqual(ImageStudy.objects.count(),before)
        self.assertEqual(LemmaImage.objects.get(pk=waiting.pk).status,'waiting')
        self.assertContains(self.client.get(self.url('word-images')),'Generate all missing pictures')

    @override_settings(COMMUNITY_DICTIONARY_IMAGE_DAILY_LIMIT=1)
    def test_more_than_fifty_are_approved_once_with_one_off_allowance_and_normal_costs(self):
        words=[self.word('word'+str(i),'meaning') for i in range(51)]
        preview=self.preview();data=self.confirmation(preview,extra_allowance='on')
        result=self.client.post(self.url('word-images'),data,follow=True)
        self.assertEqual(result.context['batch']['total'],51)
        self.assertEqual(result.context['batch']['pending'],51)
        self.assertEqual(result.context['batch']['estimate'],preview.context['estimate'])
        self.assertEqual(ImageStudy.objects.count(),51)
        self.assertEqual(LemmaImage.objects.filter(status='waiting').count(),51)
        self.assertEqual(self.client.post(self.url('word-images'),data).status_code,302)
        self.assertEqual(ImageStudy.objects.count(),51)
        for word in words[:2]:
            row=LemmaImage.objects.get(entry=word);self.run_job(row)
            self.assertEqual(row.status,'ready')
        batch=costs.batch_summary(self.d,self.owner)
        self.assertEqual(batch['finished'],2)
        self.assertEqual(batch['unknown'],0)
        self.assertEqual(pictures.daily_usage(self.d,self.owner)['account_used'],2)

    def test_removed_pictures_are_included_only_by_explicit_preview_option(self):
        removed=self.removed()
        LemmaImage.objects.filter(entry=removed).update(snapshot={})
        default=self.preview()
        self.assertFalse(default.context['preview_ready'])
        self.assertContains(default,'No missing pictures to generate with these options.')
        chosen=self.preview(include_removed='on')
        self.assertEqual([w.pk for w in chosen.context['candidates']],[removed.pk])
        self.assertContains(chosen,'Previously removed pictures are included')
        result=self.client.post(self.url('word-images'),self.confirmation(chosen),follow=True)
        self.assertEqual(result.context['batch']['total'],1)

    def test_preview_does_not_silently_include_words_added_later(self):
        original=self.word()
        preview=self.preview();later=self.word('later','later')
        result=self.client.post(self.url('word-images'),self.confirmation(preview),follow=True)
        self.assertEqual(result.context['batch']['entry_ids'],[original.pk])
        self.assertFalse(LemmaImage.objects.filter(entry=later).exists())

    def test_a_new_picture_or_changed_deliberate_decision_requires_a_new_preview(self):
        word=self.word();preview=self.preview()
        row=self.attempt(word);self.run_job(row)
        result=self.client.post(self.url('word-images'),self.confirmation(preview))
        self.assertContains(result,'Preview the batch again')
        self.assertEqual(ImageStudy.objects.count(),1)
        missing=self.attempt(self.word('missing','missing'));missing.status='failed';missing.save()
        preview=self.preview()
        missing.status='none';missing.suitability='none';missing.save()
        denied=self.client.post(self.url('word-images'),self.confirmation(preview))
        self.assertContains(denied,'no longer need a picture')
        self.assertEqual(ImageStudy.objects.count(),1)

    def test_no_silent_partial_job_when_daily_allowance_is_too_small(self):
        for i in range(21):self.word('word'+str(i),'word')
        preview=self.preview()
        denied=self.client.post(self.url('word-images'),self.confirmation(preview))
        self.assertContains(denied,'exceeds the remaining daily image allowance')
        self.assertFalse(ImageStudy.objects.exists())
        self.assertFalse(LemmaImage.objects.exists())
        membership=Membership.objects.get(dictionary=self.d,user=self.member)
        membership.role='editor';membership.save();self.client.force_login(self.member)
        preview=self.preview()
        denied=self.client.post(self.url('word-images'),self.confirmation(preview,extra_allowance='on'))
        self.assertContains(denied,'requires a dictionary owner')
        self.assertFalse(ImageStudy.objects.exists())

    def test_consent_scope_and_duplicate_previews_cannot_start_extra_attempts(self):
        self.word();preview=self.preview()
        denied=self.client.post(self.url('word-images'),self.confirmation(preview,ai_consent=''))
        self.assertContains(denied,'Confirm AI processing')
        denied=self.client.post(self.url('word-images'),self.confirmation(preview,action='generate'))
        self.assertContains(denied,'estimate expired')
        self.assertFalse(ImageStudy.objects.exists())
        first=self.confirmation(preview)
        self.client.post(self.url('word-images'),first)
        denied=self.client.post(self.url('word-images'),self.confirmation(preview))
        self.assertContains(denied,'Preview the batch again')
        self.assertEqual(ImageStudy.objects.count(),1)

    def test_large_preview_remains_complete_while_its_word_list_is_bounded(self):
        for i in range(101):self.word('word'+str(i),'word')
        page=self.preview()
        self.assertEqual(len(page.context['candidates']),101)
        self.assertEqual(len(page.context['preview_cards']),100)
        self.assertContains(page,'All 101 missing pictures are included in the estimate and approval')

    def test_new_controls_and_preview_are_localized(self):
        from django.urls import reverse
        self.word()
        for language,button,preview in [('fr','Générer toutes les images manquantes','Images manquantes dans tout le dictionnaire'),
                ('sk','Vygenerovať všetky chýbajúce obrázky','Chýbajúce obrázky v celom slovníku')]:
            self.client.post(reverse('community_dictionary:set-language'),{'language':language})
            self.assertContains(self.client.get(self.url('word-images')),button)
            self.assertContains(self.preview(),preview)

