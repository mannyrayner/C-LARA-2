"""Language ports of captured sentences, including review order and source custody."""
from unittest.mock import patch, MagicMock
from django.test import TestCase, override_settings
from django.urls import reverse
from community_dictionary import capture, port_ai, porting, port_tasks
from community_dictionary.models import Contribution, Entry, ImageWordLink, SentenceWord
from community_dictionary.participation import withdraw_all
from community_dictionary.services import add_contributions, Conflict
from community_dictionary.storage import prepare_upload
from . import test_picture_capture as capture_tests
from . import test_porting as port_tests
from .test_porting import response
from .test_workflow import recording


@override_settings(OPENAI_API_KEY='fixture-only', CREDITS_ENABLED=False,
                   COMMUNITY_DICTIONARY_PORT_WINDOW=2)
class SentencePortingTests(TestCase):
    start = capture_tests.PictureCaptureTests.start
    action = capture_tests.PictureCaptureTests.action
    ready = capture_tests.PictureCaptureTests.ready
    publish = capture_tests.PictureCaptureTests.publish
    url = capture_tests.PictureCaptureTests.url
    quote = port_tests.PortingTests.quote
    approve = port_tests.PortingTests.approve
    process = port_tests.PortingTests.process
    save = port_tests.PortingTests.save

    def setUp(self):
        capture_tests.PictureCaptureTests.setUp(self)
        self.dictionary = self.d

    def sentence(self):
        self.client.force_login(self.user)
        return self.publish(self.ready())

    def answer(self, item):
        source = item.source_entry
        translations = {'katt':'chat', 'ligga':'être couché', 'på':'sur', 'soffa':'canapé'}
        if source.entry_type == 'sentence':
            surfaces = {'katt':'Le chat', 'ligga':'est couché', 'på':'sur', 'soffa':'le canapé'}
            refs = [{'source_entry_id':r['entry'], 'surface':surfaces.get(
                Entry.objects.get(pk=r['entry']).word,'')} for r in item.snapshot['sentence_words']]
            return response(word='Le chat est couché sur le canapé.', meaning=source.meaning,
                            category='', word_links=refs)
        return response(word=translations.get(source.word,source.word), meaning=source.meaning,category='')

    def processed(self, run):
        run = self.approve(run)
        while run.items.filter(status='queued').exists():
            for item in list(run.items.filter(status='queued')):
                self.process(item,self.answer(item))
        self.assertEqual(set(run.items.values_list('status',flat=True)),{'ready'})
        return run

    def finish(self, run, sentences_first=True):
        for item in run.items.select_related('source_entry').order_by('source_entry__entry_type' if sentences_first else '-source_entry__entry_type'):
            self.save(item)

    def assert_links_and_views(self, run):
        dest = run.port.destination
        sentence = dest.entries.get(entry_type='sentence')
        links = list(capture.sentence_links(dest))
        self.assertEqual(len(links),4)
        self.assertEqual({l.surface for l in links},{'Le chat','est couché','sur','le canapé'})
        self.assertEqual(ImageWordLink.objects.filter(image__entry=sentence,sentence_text=sentence.current_text).count(),4)
        self.assertEqual(sentence.contributions.filter(kind='image',status='accepted').count(),1)
        self.assertEqual(dest.entries.filter(entry_type='word',contributions__kind='image').count(),0)
        pictures = self.client.get(reverse('community_dictionary:dictionary',args=[dest.pk]))
        self.assertEqual([c['entry'].pk for c in pictures.context['cards']],[sentence.pk])
        words = self.client.get(reverse('community_dictionary:dictionary',args=[dest.pk])+'?view=words')
        self.assertEqual(len(words.context['words']),4)
        self.assertContains(self.client.get(reverse('community_dictionary:dictionary',args=[dest.pk])+'?view=sentences'),sentence.word)
        for word in dest.entries.filter(entry_type='word'):
            self.assertEqual(capture.linked_sentences(word).get(),sentence)
            self.assertEqual(len(capture.sentence_context(sentence)['sentence_words']),4)
        for link in run.port.entry_links.all():
            self.assertEqual(link.destination_digest,porting.snapshot(link.destination)['digest'])

    def test_sentences_saved_first_have_audio_images_and_later_word_links(self):
        source=self.sentence()
        source_snapshot=porting.snapshot(source)
        run=self.approve(self.quote(language='French'))
        self.assertEqual(run.items.count(),5)
        item=run.items.get(source_entry=source)
        translate,tts=self.process(item,self.answer(item))
        self.assertEqual(translate.call_args.args[0]['entry_type'],'sentence')
        self.assertEqual(len(translate.call_args.args[0]['sentence_words']),4)
        self.assertEqual(tts.call_args.kwargs['speech_kind'],'sentence')
        self.assertEqual(tts.call_args.kwargs['language'],'fr')
        self.assertFalse(run.port.destination.entries.exists())
        dest=self.save(item)
        self.assertEqual(dest.entry_type,'sentence')
        self.assertTrue(dest.contributions.filter(kind='audio',status='accepted').exists())
        while run.items.filter(status='queued').exists():
            for other in list(run.items.filter(status='queued')):
                self.process(other,self.answer(other));self.save(other)
        self.assert_links_and_views(run)
        self.assertEqual(porting.snapshot(source),source_snapshot)
        self.assertTrue(run.port.destination.sentence_capture_enabled)

    def test_words_saved_first_and_incremental_update_skips_unchanged(self):
        self.sentence();run=self.processed(self.quote(language='French'))
        self.finish(run,sentences_first=False)
        self.assert_links_and_views(run)
        update=self.quote(language='French',port=run.port)
        self.assertEqual(update.items.count(),0)
        self.assertEqual(update.skipped,5)
        self.assertEqual(update.protected,0)

    def test_sentence_with_no_vocabulary_is_not_omitted(self):
        source=self.sentence()
        SentenceWord.objects.filter(sentence_text=source.current_text).delete()
        self.d.entries.filter(entry_type='word').update(archived=True)
        run=self.processed(self.quote(language='French'))
        self.assertEqual(run.items.count(),1)
        dest=self.save(run.items.get())
        self.assertEqual(dest.entry_type,'sentence')
        self.assertTrue(dest.selected_image)

    def test_commenting_only_preserves_sentence_and_recording(self):
        source=self.sentence()
        audio=add_contributions(source,self.owner,{'prepared_audio':prepare_upload(recording(),'audio')},[],publish=True)[0]
        run=self.approve(self.quote(language='Swedish',explanation='French'))
        for item in list(run.items.all()):
            _,tts=self.process(item,self.answer(item))
            self.assertFalse(tts.called)
            self.save(item)
        dest=run.port.destination.entries.get(entry_type='sentence')
        self.assertEqual(dest.word,source.word)
        self.assertEqual(dest.current_text.author,source.current_text.author)
        self.assertEqual(dest.contributions.get(kind='audio').shared_from_id,audio.pk)
        self.assertEqual(set(capture.sentence_links(run.port.destination).values_list('surface',flat=True)),
                         {'Katten','ligger','på','soffan'})

    def test_incremental_changed_word_and_sentence_do_not_block_each_other(self):
        source=self.sentence();run=self.processed(self.quote(language='French'));self.finish(run)
        word=self.d.entries.get(word='katt')
        add_contributions(word,self.owner,{'meaning':'domestic cat','edit_text':True},[],publish=True)
        update=self.processed(self.quote(language='French',port=run.port))
        self.assertEqual(update.items.count(),2)
        self.finish(update,sentences_first=False)
        self.assert_links_and_views(update)
        next_run=self.quote(language='French',port=run.port)
        self.assertEqual(next_run.items.count(),0)

    def test_editing_sentence_discards_audio_and_positions_but_keeps_related_words(self):
        self.sentence();run=self.processed(self.quote(language='French'))
        for item in run.items.select_related('source_entry'):
            if item.source_entry.entry_type=='sentence':
                sentence=self.save(item,word='Le chat se repose sur le canapé.')
            else:self.save(item)
        self.assertFalse(sentence.contributions.filter(kind='audio').exists())
        self.assertEqual(set(capture.sentence_links(run.port.destination).values_list('surface',flat=True)),{''})
        self.assertEqual(capture.sentence_links(run.port.destination).count(),4)
        update=self.quote(language='French',port=run.port)
        self.assertEqual(update.protected,1)

    def test_source_vocabulary_change_invalidates_sentence_preview(self):
        source=self.sentence();run=self.processed(self.quote(language='French'))
        item=run.items.get(source_entry=source)
        word=self.d.entries.get(word='katt')
        self.assertTrue(item.sources.filter(pk=word.current_text_id).exists())
        add_contributions(word,self.owner,{'word':'katten','edit_text':True},[],publish=True)
        with self.assertRaises(Conflict):self.save(item)

    def test_source_withdrawal_removes_previews_and_saved_derivatives(self):
        self.sentence();run=self.processed(self.quote(language='French'))
        sentence_item=run.items.get(source_entry__entry_type='sentence')
        dest=self.save(sentence_item)
        withdraw_all(self.user,self.d.pk,0)
        self.assertFalse(dest.contributions.filter(status='accepted').exists())
        self.assertFalse(run.items.filter(status='ready').exists())

    def test_existing_word_only_results_can_be_finished_then_sentences_added(self):
        source=self.sentence();run=self.quote(language='French')
        # Exactly the old quote shape: no sentence item, unchanged word snapshots.
        run.items.filter(source_entry=source).delete()
        run=self.processed(run)
        self.finish(run)
        update=self.quote(language='French',port=run.port)
        self.assertEqual(update.items.count(),1)
        self.assertEqual(update.items.get().source_entry,source)
        self.assertEqual(update.skipped,4)
        update=self.processed(update);self.finish(update)
        self.assert_links_and_views(update)

    def test_progress_and_empty_destination_point_to_review(self):
        self.sentence();run=self.processed(self.quote(language='French'))
        page=self.client.get(self.url('port-run',run.pk))
        self.assertContains(page,'5 ready to review')
        self.assertContains(page,'0 saved in this run')
        self.assertContains(page,'Continue reviewing and saving')
        url=reverse('community_dictionary:dictionary',args=[run.port.destination_id])
        self.assertContains(self.client.get(url),'Review and save language results')
        form=self.client.get(self.url('port-review',run.pk,run.items.get(source_entry__entry_type='sentence').pk))
        self.assertEqual(form.context['form'].fields['word'].label,'Sentence')
        self.finish(run)
        self.assertNotContains(self.client.get(url),'Review and save language results')

    def test_sentence_schema_rejects_foreign_ids_and_drops_invented_positions(self):
        data={'entry_type':'sentence','sentence_words':[{'source_entry_id':1}]}
        good=response(word='Le chat dort.',word_links=[{'source_entry_id':1,'surface':'chat'}])
        self.assertEqual(port_ai.parse(good,data)['word_links'][0]['surface'],'chat')
        bad=response(word='Le chat dort.',word_links=[{'source_entry_id':99,'surface':'chat'}])
        with self.assertRaises(ValueError):port_ai.parse(bad,data)
        dup=response(word='Le chat dort.',word_links=[{'source_entry_id':1,'surface':'chat'}]*2)
        with self.assertRaises(ValueError):port_ai.parse(dup,data)
        wrong=response(word='Le chat dort.',word_links=[{'source_entry_id':1,'surface':'katten'}])
        self.assertEqual(port_ai.parse(wrong,data)['word_links'][0]['surface'],'')

    def test_sentence_provider_contract_bounded_and_private(self):
        client=MagicMock()
        with patch.object(port_ai,'_openai_client',return_value=client):
            port_ai.translate({'entry_type':'sentence','sentence_words':[]},None,model='fixture',api_key='fixture')
        args=client.__enter__.return_value.responses.create.call_args.kwargs
        self.assertFalse(args['store'])
        self.assertEqual(args['max_output_tokens'],2800)
        self.assertEqual(args['text']['format']['schema'],port_ai.SENTENCE_SCHEMA)
        self.assertIn('complete translated sentence',args['instructions'])

    def test_sentence_speech_recipe_is_frozen_in_estimate_and_saved_provenance(self):
        self.sentence();run=self.quote(language='French')
        from community_dictionary import pronunciation
        self.assertEqual(run.prices['sentence_speech_recipe'],pronunciation.SENTENCE_VERSION)
        with patch.object(pronunciation,'SENTENCE_VERSION','changed-fixture'):
            with self.assertRaises(Conflict):self.approve(run)
        run=self.processed(run)
        dest=self.save(run.items.get(source_entry__entry_type='sentence'))
        self.assertEqual(dest.contributions.get(kind='audio').provenance['instructions_version'],pronunciation.SENTENCE_VERSION)

    def test_sentence_audio_timeout_leaves_translated_text_saveable(self):
        self.sentence();run=self.approve(self.quote(language='French'))
        item=run.items.get(source_entry__entry_type='sentence')
        with patch.object(port_ai,'translate',return_value=self.answer(item)), \
                patch('community_dictionary.tts.synthesize',side_effect=TimeoutError), \
                patch('community_dictionary.port_tasks.send'):
            port_tasks.process_item(item.pk)
        item.refresh_from_db()
        self.assertEqual(item.status,'ready')
        self.assertEqual(item.file_path,'')
        dest=self.save(item)
        self.assertEqual(dest.word,'Le chat est couché sur le canapé.')
        self.assertFalse(dest.contributions.filter(kind='audio').exists())

    def test_destination_preview_link_is_private_to_the_authorised_owner(self):
        self.sentence();run=self.processed(self.quote(language='French'))
        from community_dictionary.models import Membership
        dest=run.port.destination
        Membership.objects.create(dictionary=dest,user=self.user,accepted=True)
        self.client.force_login(self.user)
        page=self.client.get(reverse('community_dictionary:dictionary',args=[dest.pk]))
        self.assertNotContains(page,'Review and save language results')
        self.assertEqual(self.client.get(self.url('port-run',run.pk)).status_code,404)
