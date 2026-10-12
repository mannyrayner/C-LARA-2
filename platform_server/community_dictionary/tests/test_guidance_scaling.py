"""Realistic image lineage and cold-request query budgets; no provider calls."""
from contextlib import nullcontext
import time
import uuid
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from community_dictionary import porting, port_categories, port_vocabulary as vocab, workflow
from community_dictionary.models import (Dictionary, Entry, Contribution, LanguagePort,
    PortRun, PortItem, PortEntryLink, SentenceWord, ImageWordLink, VocabularyState)
from community_dictionary.lexicon import described_picture_sources
from community_dictionary.workflow_data import reading


@override_settings(OPENAI_API_KEY='fixture-only',CREDITS_ENABLED=False,
    PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class GuidanceScalingTests(TestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_user('owner',password='fixture-only')
        self.source = Dictionary.objects.create(owner=self.owner,name='Swedish',language='Swedish',explanation_language='English',sentence_capture_enabled=True)
        self.target = Dictionary.objects.create(owner=self.owner,name='French',language='French',explanation_language='English',sentence_capture_enabled=True)
        self.port = LanguagePort.objects.create(source=self.source,destination=self.target,user=self.owner,
            name='French',language='French',explanation_language='English')
        self.batch = LanguagePort.objects.create(source=self.source,user=self.owner,is_description_batch=True,
            name='Swedish',language='Swedish',explanation_language='English')
        self.run = PortRun.objects.create(port=self.port,status='complete',stage='sentences',expires_at=timezone.now(),
            source_language='Swedish',source_explanation_language='English')
        self.batch_run = PortRun.objects.create(port=self.batch,status='complete',stage='descriptions',expires_at=timezone.now(),
            source_language='Swedish',source_explanation_language='English')
        self.words = {d.pk:[self.entry(d,f'word-{n}','word') for n in range(3)] for d in [self.source,self.target]}
        self.client.force_login(self.owner)

    def entry(self,dictionary,word='',kind='word'):
        entry = Entry.objects.create(dictionary=dictionary,created_by=self.owner,entry_type=kind)
        if word:
            entry.word=word;entry.meaning='fixture meaning'
            entry.current_text=Contribution.objects.create(entry=entry,author=self.owner,kind='text',text_field='word',status='accepted',word=word,
                provenance={'sentence_vocabulary':kind=='word'})
            entry.current_meaning=Contribution.objects.create(entry=entry,author=self.owner,kind='text',text_field='meaning',status='accepted',meaning=entry.meaning)
            entry.save()
        return entry

    def image(self,entry,parent=None):
        picture=Contribution.objects.create(entry=entry,author=self.owner,kind='image',status='accepted',
            file_path=parent.file_path if parent else f'{entry.dictionary_id}/{uuid.uuid4().hex}.jpg',mime_type='image/jpeg',shared_from=parent)
        entry.selected_image=picture;entry.save(update_fields=['selected_image'])
        return picture

    def vocabulary(self,entry):
        words=[]
        for word in self.words[entry.dictionary_id]:
            SentenceWord.objects.create(sentence_text=entry.current_text,word_entry=word,word_text=word.current_text,surface='fixture')
            ImageWordLink.objects.create(image=entry.selected_image,word_entry=word,sentence_text=entry.current_text,created_by=self.owner)
            words.append({'entry':word.pk,'text':word.current_text_id,'meaning':word.current_meaning_id})
        VocabularyState.objects.create(sentence=entry,snapshot=vocab.sentence_snapshot(entry),recipe=vocab.VERSION,words=words,accepted_by=self.owner)

    def pair(self,n):
        original=self.entry(self.source);original_image=self.image(original)
        source=self.entry(self.source,f'En mening {n}.','sentence');source_image=self.image(source,original_image)
        target=self.entry(self.target,f'Une phrase {n}.','sentence');self.image(target,source_image)
        self.vocabulary(source);self.vocabulary(target)
        snap=porting.snapshot(source,sentence_only=True)
        PortEntryLink.objects.create(port=self.port,source=source,destination=target,
            source_digest=port_categories.digest(snap,None),destination_digest=porting.snapshot(target,sentence_only=True)['digest'])
        PortItem.objects.create(run=self.run,source_entry=source,status='saved',snapshot=snap)
        PortItem.objects.create(run=self.batch_run,source_entry=original,source_image=original_image,saved_entry=source,status='saved')
        return original,source,target

    def measured_home(self,legacy=False):
        started=time.perf_counter()
        with patch('community_dictionary.workflow.reading',nullcontext) if legacy else nullcontext():
            with patch('community_dictionary.workflow_data.reading',nullcontext) if legacy else nullcontext():
                with CaptureQueriesContext(connection) as queries:
                    response=self.client.get(reverse('community_dictionary:home'))
        self.assertEqual(response.status_code,200)
        self.assertNotContains(response,'new sentences')
        return len(queries),time.perf_counter()-started

    def test_150_sentence_pair_cold_home_query_budget_and_equivalent_snapshots(self):
        pairs=[self.pair(n) for n in range(5)]
        small=self.measured_home()
        pairs.extend(self.pair(n) for n in range(5,150))
        legacy=self.measured_home(legacy=True)
        large=self.measured_home()
        again=self.measured_home()
        print(f'Guidance home: 5 sentences={small}; 150 before bulk reads={legacy}; 150 repaired={large}; second cold request={again}')
        self.assertLess(large[0],130)
        self.assertLessEqual(large[0],small[0]+5)
        self.assertEqual(again[0],large[0])
        source,target=pairs[-1][1:]
        exact=[porting.snapshot(source),porting.snapshot(source,sentence_only=True),
               porting.snapshot(target),vocab.sentence_snapshot(target),vocab.current_state(target)]
        with reading():
            self.assertEqual(exact,[porting.snapshot(source),porting.snapshot(source,sentence_only=True),
                porting.snapshot(target),vocab.sentence_snapshot(target),vocab.current_state(target)])
        # A separate request must immediately see an edit: no process/TTL cache.
        target.current_text.word='Correction';target.current_text.save(update_fields=['word'])
        target.word='Correction';target.save(update_fields=['word'])
        with reading():
            self.assertFalse(vocab.current_state(target))
            self.assertNotEqual(exact[2],porting.snapshot(target))

    def test_sibling_and_grandparent_image_copies_hide_only_redundant_blank_cards(self):
        original,source,target=self.pair(1)
        blank=self.entry(self.target);copy=self.image(blank,original.selected_image)
        self.assertIn(blank.pk,described_picture_sources(self.target).values_list('pk',flat=True))
        normal=self.client.get(reverse('community_dictionary:dictionary',args=[self.target.pk]))
        self.assertNotIn(blank.pk,[e.pk for e in normal.context['page']])
        self.assertIn(target.pk,[e.pk for e in normal.context['page']])
        all_entries=self.client.get(reverse('community_dictionary:dictionary',args=[self.target.pk])+'?show=all')
        self.assertIn(blank.pk,[e.pk for e in all_entries.context['page']])
        self.assertTrue(Entry.objects.filter(pk=blank.pk,archived=False).exists())
        self.target.public_browsing_enabled=True;self.target.save(update_fields=['public_browsing_enabled'])
        visitor=self.client.get(reverse('community_dictionary:public-dictionary',args=[self.target.pk]))
        self.assertNotIn(blank.pk,[row['id'] for row in visitor.context['rows']])
        self.assertIn(target.pk,[row['id'] for row in visitor.context['rows']])
        # Independent material is never hidden, even with the same image family.
        note=Contribution.objects.create(entry=blank,author=self.owner,kind='note',status='accepted',body='Discussion')
        self.assertNotIn(blank.pk,described_picture_sources(self.target).values_list('pk',flat=True))
        note.delete()
        target.archived=True;target.save(update_fields=['archived'])
        self.assertNotIn(blank.pk,described_picture_sources(self.target).values_list('pk',flat=True))

    def test_ready_translation_reviews_have_bounded_queries_and_recheck_edits(self):
        pairs=[self.pair(n) for n in range(50)]
        digests=dict(self.port.entry_links.values_list('source_id','destination_digest'))
        items=list(self.run.items.all())
        for item in items:
            item.status='ready';item.destination_digest=digests[item.source_entry_id]
        PortItem.objects.bulk_update(items,['status','destination_digest'])
        with CaptureQueriesContext(connection) as queries:
            offer=workflow.suggestion(self.owner,self.target)
        print('Ready-review guidance queries:',len(queries))
        self.assertEqual(offer['label'],'50 sentences ready to review')
        self.assertLess(len(queries),40)
        target=pairs[-1][2]
        target.current_text.word='Changed';target.current_text.save(update_fields=['word'])
        target.word='Changed';target.save(update_fields=['word'])
        self.assertEqual(workflow.suggestion(self.owner,self.target)['label'],'49 sentences ready to review')

    def test_unrelated_same_file_and_cyclic_lineage_are_not_hidden(self):
        _,_,target=self.pair(1)
        blank=self.entry(self.target);copy=self.image(blank)
        copy.file_path=target.selected_image.file_path;copy.save(update_fields=['file_path'])
        self.assertNotIn(blank.pk,described_picture_sources(self.target).values_list('pk',flat=True))
        copy.shared_from=copy;copy.save(update_fields=['shared_from'])
        self.assertNotIn(blank.pk,described_picture_sources(self.target).values_list('pk',flat=True))

    def test_shared_ai_style_does_not_merge_different_generated_pictures(self):
        style_entry=self.entry(self.target);style=self.image(style_entry)
        style.provenance={'origin':'generated','role':'dictionary_style'};style.save(update_fields=['provenance'])
        original=self.entry(self.target);picture=self.image(original,style)
        picture.provenance={'origin':'generated','source_style_id':style.pk}
        picture.save(update_fields=['provenance'])
        picture.file_path='different-original.jpg';picture.save(update_fields=['file_path'])
        sentence=self.entry(self.target,'Une autre image.','sentence');other=self.image(sentence,style)
        other.file_path='different-sentence.jpg';other.save(update_fields=['file_path'])
        hidden=set(described_picture_sources(self.target).values_list('pk',flat=True))
        self.assertNotIn(original.pk,hidden)
        self.assertNotIn(style_entry.pk,hidden)
