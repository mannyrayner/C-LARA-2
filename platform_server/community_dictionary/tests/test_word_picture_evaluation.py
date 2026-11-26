"""Review the actual word-page picture without changing content or legacy sets."""
import csv
import io
import random
import uuid
from unittest.mock import patch

from django.test import TestCase

from community_dictionary import evaluation as ev, lemma_images
from community_dictionary.models import (Contribution, EvaluationItem, EvaluationRating,
    EvaluationSession, EvaluationSet, EvaluationUnit, LemmaImage)
from community_dictionary.storage import prepare_upload, write_upload
from . import test_evaluation as fixtures
from .test_workflow import picture, recording


class WordPictureEvaluationTests(TestCase):
    setUp = fixtures.EvaluationTests.setUp
    skills = fixtures.EvaluationTests.skills
    make_entry = fixtures.EvaluationTests.make_entry
    link = fixtures.EvaluationTests.link
    batch = fixtures.EvaluationTests.batch
    item_url = fixtures.EvaluationTests.item_url
    save_data = fixtures.EvaluationTests.save_data
    close = fixtures.EvaluationTests.close

    def illustrated(self, text='hund', meaning='dog', suitability='clue'):
        entry = self.make_entry(text, meaning, kind='word')
        # The generated lemma picture is deliberately different from selected_image.
        image = Contribution.objects.create(entry=entry, author=self.owner, kind='image',
            status='accepted', provenance={'origin': 'generated', 'model': 'fixture-image-model'},
            **write_upload(prepare_upload(picture(), 'image'), self.dictionary.pk, []))
        decision = LemmaImage.objects.create(entry=entry, image=image, status='ready',
            suitability=suitability, requested_by=self.owner, snapshot=lemma_images.basis(entry))
        return entry, image, decision

    def start(self, batch, user=None, dims=None):
        user = user or self.member
        skills = ev.competence_snapshot(user, batch)
        return EvaluationSession.objects.create(evaluation_set=batch, user=user, competences=skills,
            dimensions=dims or ev.eligible_dimensions(skills, batch.scope, batch.rubric), involvement='no')

    def exported(self, batch):
        response = self.owner_client.get(fixtures.url('evaluation-export', self.dictionary.pk, batch.pk))
        self.assertEqual(response.status_code, 200)
        return list(csv.DictReader(io.StringIO(response.content.decode())))

    def test_reproducible_sample_uses_current_pictures_and_both_clue_classes(self):
        entries = [self.illustrated(f'word {i}', f'meaning {i}',
            'illustration' if i % 2 else 'clue') for i in range(25)]
        hidden, _, decision = self.illustrated('hidden')
        decision.status = 'removed'; decision.save()
        stale, _, decision = self.illustrated('stale')
        decision.snapshot = {}; decision.save()
        absent = self.make_entry('without a picture', '', kind='word', image=False)
        with patch.object(lemma_images, 'analyse') as analyse, patch.object(lemma_images.images, 'generate') as generate:
            batch = self.batch(scope='word_pics', sampling='random', size=20)
            analyse.assert_not_called(); generate.assert_not_called()
        expected = random.Random(batch.seed).sample(batch.population_ids, 20)
        self.assertEqual(list(batch.items.values_list('entry_id', flat=True)), expected)
        self.assertEqual(set(batch.population_ids), {entry.pk for entry, _, _ in entries})
        self.assertFalse({hidden.pk, stale.pk, absent.pk} & set(batch.population_ids))
        self.assertEqual((batch.scope, batch.rubric), ('words', ev.PICTURE_RUBRIC))
        self.assertEqual(set(batch.units.values_list('dimension', flat=True)), set(ev.PICTURE_DIMENSIONS))
        actual_images = {entry.pk: image.pk for entry, image, _ in entries}
        for item in batch.items.all():
            self.assertEqual(item.snapshot['entry']['image']['id'], actual_images[item.entry_id])
            self.assertEqual(item.snapshot['words'], [])
            self.assertIsNone(item.snapshot['entry']['audio'])

    def test_old_word_sets_keep_their_projection_and_dimensions(self):
        entry, image, decision = self.illustrated()
        # A persisted pre-combination set, without calling today's set creator.
        old = EvaluationSet.objects.create(dictionary=self.dictionary, created_by=self.owner,
            name='Earlier word set', scope='words', sampling='all', seed='earlier',
            language=self.dictionary.language, explanation_language=self.dictionary.explanation_language,
            population_ids=[entry.pk], rubric=ev.RUBRIC)
        snapshot = ev.graph(self.dictionary)[entry.pk]
        item = EvaluationItem.objects.create(evaluation_set=old, entry=entry, position=1,
            snapshot=snapshot, fingerprint=ev.digest(snapshot))
        for dim in ('word_translation', 'word_audio'):
            EvaluationUnit.objects.create(evaluation_set=old, item=item, dimension=dim, key=dim)
        self.assertNotEqual(item.snapshot['entry']['image']['id'], image.pk)
        decision.status = 'removed'; decision.save()
        self.assertTrue(ev.is_current(item, ev.graph_for_set(old)))
        self.assertEqual(set(old.units.values_list('dimension', flat=True)), {'word_translation', 'word_audio'})
        self.assertEqual(old.rubric, ev.RUBRIC)

    def test_combined_word_pages_cover_all_material_and_keep_unpictured_words(self):
        entry, image, _ = self.illustrated()
        batch = self.batch(scope='words')
        self.assertEqual(batch.rubric, ev.WORD_PAGE_RUBRIC)
        pictured = batch.items.get(entry=entry)
        unpictured = batch.items.get(entry=self.word)
        self.assertEqual(pictured.snapshot['entry']['image']['id'], image.pk)
        self.assertIsNotNone(pictured.snapshot['entry']['audio'])
        self.assertEqual(set(pictured.units.values_list('dimension', flat=True)),
            {'word_translation', 'word_audio', *ev.PICTURE_DIMENSIONS})
        self.assertEqual(set(unpictured.units.filter(missing=True).values_list('dimension', flat=True)),
            set(ev.PICTURE_DIMENSIONS))
        self.start(batch)
        response = self.client.get(self.item_url(batch, pictured))
        self.assertContains(response, 'Word translation')
        self.assertContains(response, 'Word audio')
        self.assertContains(response, 'Cultural suitability')
        self.assertEqual(response.content.decode().count('<img '), 1)
        self.assertEqual(self.client.post(self.item_url(batch, pictured),
            self.save_data(pictured)).status_code, 302)
        self.assertEqual(EvaluationRating.objects.count(), 6)
        self.close(batch)
        rows = self.exported(batch)
        self.assertEqual({r['dimension'] for r in rows}, {'word_translation', 'word_audio', *ev.PICTURE_DIMENSIONS})
        self.assertTrue(all(r['score'] == '' for r in rows if r['missing_material'] == 'True'))

    def test_combined_competence_and_picture_changes_are_checked(self):
        entry, _, decision = self.illustrated()
        batch = self.batch(scope='words')
        self.skills(self.member, listening=0, explanation=0)
        skills = ev.competence_snapshot(self.member, batch)
        self.assertEqual(ev.eligible_dimensions(skills, batch.scope, batch.rubric), list(ev.PICTURE_DIMENSIONS))
        self.skills(self.member, reading=1)
        self.assertEqual(ev.eligible_dimensions(ev.competence_snapshot(self.member, batch),
            batch.scope, batch.rubric), [])
        item = batch.items.get(entry=entry)
        decision.status = 'removed'; decision.save()
        self.assertFalse(ev.is_current(item, ev.graph_for_set(batch)))

    def test_owner_creation_link_defaults_and_empty_population(self):
        address = fixtures.url('evaluation-home', self.dictionary.pk)
        response = self.owner_client.get(address + '?scope=word_pics')
        self.assertEqual(response.context['form'].initial['size'], 20)
        self.assertEqual(response.context['form'].initial['scope'], 'word_pics')
        self.assertContains(response, 'Word pictures only')
        data = {'token': uuid.uuid4(), 'name': 'Picture pilot', 'scope': 'word_pics',
                'sampling': 'random', 'size': 20}
        self.assertEqual(self.client.post(address, data).status_code, 404)
        self.assertContains(self.owner_client.post(address, data),
            'There are no current accepted word pictures', status_code=409)
        self.illustrated()
        self.assertEqual(self.owner_client.post(address, data).status_code, 302)
        self.assertContains(self.owner_client.get(fixtures.url('dictionary', self.dictionary.pk) + '?view=words'),
            'Review a sample of word pictures')
        self.assertNotContains(self.client.get(fixtures.url('dictionary', self.dictionary.pk) + '?view=words'),
            'Review a sample of word pictures')

    def test_competence_start_render_save_hidden_results_and_export(self):
        entry, image, _ = self.illustrated()
        batch = self.batch(scope='word_pics')
        address = fixtures.url('evaluation-set', self.dictionary.pk, batch.pk)
        self.skills(self.member, reading=1)
        self.assertEqual(self.client.get(address).context['eligible'], [])
        self.skills(self.member, listening=0, explanation=0)
        response = self.client.get(address)
        self.assertEqual(response.context['eligible'], list(ev.PICTURE_DIMENSIONS))
        self.assertEqual(self.client.post(address, {'dimensions': list(ev.PICTURE_DIMENSIONS),
            'involvement': 'no', 'consent': 'on'}).status_code, 302)
        item = batch.items.get()
        response = self.client.get(self.item_url(batch))
        html = response.content.decode()
        self.assertContains(response, 'Intended meaning:')
        self.assertContains(response, 'dog')
        self.assertContains(response, 'Cultural suitability')
        # Titles belong inside the panel; the judgement has its own associated label.
        self.assertNotContains(response, '<legend>')
        for row in response.context['rows']:
            self.assertContains(response, f'<h2 id="evaluation-heading-{row["unit"].pk}">')
            self.assertContains(response, f'<label for="{row["score"].id_for_label}">Your judgement</label>')
        self.assertEqual(html.count('<img '), 1)
        self.assertNotContains(response, 'fixture-image-model')
        self.assertNotContains(response, 'AI-generated')
        self.assertEqual(self.client.post(self.item_url(batch), self.save_data(item, score='minor')).status_code, 302)
        self.assertEqual(EvaluationRating.objects.count(), 4)
        self.assertEqual(self.owner_client.get(fixtures.url('evaluation-results', self.dictionary.pk, batch.pk)).status_code, 409)
        self.close(batch)
        rows = self.exported(batch)
        self.assertEqual({row['dimension'] for row in rows}, set(ev.PICTURE_DIMENSIONS))
        self.assertTrue(all(row['image_contribution_id'] == str(image.pk) for row in rows))
        self.assertTrue(all(row['image_origin'] == 'generated' for row in rows))
        self.assertTrue(all(row['score'] == 'minor' for row in rows))

    def test_picture_replacement_blocks_new_ratings_and_retains_original_results(self):
        entry, image, decision = self.illustrated()
        batch = self.batch(scope='word_pics'); self.start(batch)
        item = batch.items.get()
        self.assertEqual(self.client.post(self.item_url(batch), self.save_data(item)).status_code, 302)
        # Changing unrelated word audio must not invalidate an image judgement.
        Contribution.objects.create(entry=entry, author=self.owner, kind='audio', status='accepted',
            **write_upload(prepare_upload(recording(), 'audio'), self.dictionary.pk, []))
        self.assertTrue(ev.is_current(item, ev.graph_for_set(batch)))
        decision.image_id = entry.selected_image_id; decision.save()
        self.assertEqual(self.client.post(self.item_url(batch), self.save_data(item, revision=1)).status_code, 409)
        self.close(batch)
        self.assertTrue(all(row['image_contribution_id'] == str(image.pk) for row in self.exported(batch)))
        self.assertEqual(ev.result_data(batch)['changed'], 1)
        image.status = 'withdrawn'; image.save()
        self.assertEqual(self.exported(batch), [])
        media = fixtures.url('evaluation-media', self.dictionary.pk, batch.pk, item.pk, image.pk)
        self.assertEqual(self.client.get(media).status_code, 404)

    def test_signed_in_visitor_needs_explicit_access_and_consent(self):
        _, image, _ = self.illustrated()
        self.dictionary.public_browsing_enabled = True; self.dictionary.save()
        private = self.batch(scope='word_pics')
        self.assertEqual(self.visitor.get(fixtures.url('evaluation-set', self.dictionary.pk, private.pk)).status_code, 404)
        batch = self.batch(scope='word_pics', allow_visitors=True)
        address = fixtures.url('evaluation-set', self.dictionary.pk, batch.pk)
        item = batch.items.get()
        media = fixtures.url('evaluation-media', self.dictionary.pk, batch.pk, item.pk, image.pk)
        self.assertEqual(self.visitor.get(media).status_code, 404)
        data = {'dimensions': ['word_picture'], 'involvement': 'no'}
        self.assertEqual(self.visitor.post(address, data).status_code, 200)
        data['consent'] = 'on'
        self.assertEqual(self.visitor.post(address, data).status_code, 302)
        response = self.visitor.get(media)
        self.assertEqual(response.status_code, 200); response.close()
        self.assertEqual(self.visitor.get(fixtures.url('evaluation-results', self.dictionary.pk, batch.pk)).status_code, 404)
        self.dictionary.public_browsing_enabled = False; self.dictionary.save()
        self.assertEqual(self.visitor.get(media).status_code, 404)
