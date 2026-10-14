"""Evaluation security, frozen versions, rating workflow and statistical examples."""
import csv
import io
import random
import re
import uuid
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import Client, TestCase, SimpleTestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from community_dictionary import evaluation as ev
from community_dictionary.evaluation_views import csv_cell
from community_dictionary.models import (CommunityProfile, Contribution, Dictionary, Entry,
    EvaluationItem, EvaluationProgress, EvaluationRating, EvaluationSession, EvaluationSet,
    EvaluationUnit, LanguageCompetence, Membership, Participation, SentenceWord, WithdrawalHold)
from community_dictionary.services import Conflict, accept
from community_dictionary.storage import prepare_upload, write_upload
from . import test_workflow as workflow
from .test_workflow import picture, recording


def url(name, *args):
    return reverse('community_dictionary:' + name, args=args)


class EvaluationTests(TestCase):
    def setUp(self):
        workflow.WorkflowTests.setUp(self)
        self.dictionary.explanation_language = 'English'
        self.dictionary.save()
        self.owner_client = Client(); self.owner_client.force_login(self.owner)
        self.visitor = Client(); self.visitor.force_login(self.outsider)
        self.guest = Client()
        self.word = self.make_entry('katt', 'cat', kind='word', image=False)
        self.sentence = self.make_entry('Katten ligger på soffan.', 'The cat is on the sofa.')
        self.link(self.sentence, self.word, 'Katten')
        for user in [self.owner, self.member, self.third, self.outsider]:
            self.skills(user)

    def skills(self, user, reading=3, listening=3, explanation=3):
        for language, r, l in [('Swedish', reading, listening), ('English', explanation, explanation)]:
            LanguageCompetence.objects.update_or_create(user=user, language_key=ev.language_key(language),
                defaults={'language': language, 'reading': r, 'listening': l})

    def make_entry(self, text, translation, kind='sentence', image=True, audio=True, author=None):
        author = author or self.owner
        entry = Entry.objects.create(dictionary=self.dictionary, created_by=author, entry_type=kind)
        for field, value in [('word', text), ('meaning', translation)]:
            if value:
                c = Contribution.objects.create(entry=entry, author=author, kind='text', text_field=field,
                    **{field: value}, provenance={'origin': 'human'})
                accept(c, self.owner)
        if image:
            c = Contribution.objects.create(entry=entry, author=author, kind='image',
                **write_upload(prepare_upload(picture(), 'image'), self.dictionary.pk, []))
            accept(c, self.owner)
        if audio:
            c = Contribution.objects.create(entry=entry, author=author, kind='audio',
                **write_upload(prepare_upload(recording(), 'audio'), self.dictionary.pk, []))
            accept(c, self.owner)
        entry.refresh_from_db()
        return entry

    def link(self, sentence, word, surface):
        SentenceWord.objects.create(sentence_text=sentence.current_text, word_entry=word,
                                   word_text=word.current_text, surface=surface)

    def batch(self, **extra):
        return ev.create_set(self.owner, self.dictionary, {'token': uuid.uuid4(), 'name': 'Quality pilot',
            'scope': 'sentences', 'sampling': 'all', 'size': 30, 'allow_visitors': False, **extra})

    def start(self, batch, user=None, dims=None):
        user = user or self.member
        skills = ev.competence_snapshot(user, batch)
        return EvaluationSession.objects.create(evaluation_set=batch, user=user, competences=skills,
            dimensions=dims or ev.eligible_dimensions(skills, batch.scope), involvement='no')

    def item_url(self, batch, item=None):
        return url('evaluation-item', self.dictionary.pk, batch.pk, (item or batch.items.first()).pk)

    def save_data(self, item, score='ok', revision=0, session=None):
        data = {'action': 'save', 'revision': revision}
        for unit in item.units.filter(missing=False):
            if session is None or unit.dimension in session.dimensions:
                data[f'score_{unit.pk}'] = score
                data[f'comment_{unit.pk}'] = ''
        return data

    def close(self, batch):
        return self.owner_client.post(url('evaluation-close', self.dictionary.pk, batch.pk), {'confirm': 'yes'})

    def test_profile_private_and_only_own_data_updated(self):
        response = self.client.post(url('evaluation-languages'), {'language': '  SWEDISH  ',
            'reading': 2, 'listening': 1, 'variety': 'PRIVATE-VARIETY', 'experience': 'PRIVATE-EXPERIENCE'})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(LanguageCompetence.objects.filter(user=self.member).count(), 2)
        saved = LanguageCompetence.objects.get(user=self.member, language_key='swedish')
        self.assertEqual((saved.reading, saved.listening), (2, 1))
        self.assertContains(self.client.get(url('evaluation-languages') + '?language=Swedish'), 'value="PRIVATE-VARIETY"')
        self.assertEqual(LanguageCompetence.objects.get(user=self.owner, language_key='swedish').reading, 3)
        CommunityProfile.objects.create(user=self.member, public_name='Public reader', list_as_contributor=True)
        for address in [url('about'), url('contributor', self.member.pk)]:
            self.assertNotContains(self.guest.get(address), 'PRIVATE-VARIETY')
        self.assertNotContains(self.owner_client.get(url('evaluation-languages')), 'PRIVATE-EXPERIENCE')
        self.assertEqual(self.guest.get(url('evaluation-languages')).status_code, 302)
        self.assertContains(self.client.get(url('profile')), 'Language competences for evaluation')

    def test_competence_validation_and_task_specific_eligibility(self):
        self.skills(self.member, listening=1, explanation=1)
        skills = ev.competence_snapshot(self.member, self.dictionary)
        self.assertEqual(ev.eligible_dimensions(skills, 'sentences'), ['image', 'language', 'vocabulary'])
        self.assertEqual(ev.eligible_dimensions(skills, 'words'), [])
        self.skills(self.member, reading=1)
        self.assertEqual(ev.eligible_dimensions(ev.competence_snapshot(self.member, self.dictionary), 'sentences'), [])
        self.assertEqual(self.client.post(url('evaluation-languages'), {'language': ' ', 'reading': 99, 'listening': 3}).status_code, 200)
        self.assertFalse(LanguageCompetence.objects.filter(reading=99).exists())

    def test_create_requires_owner_and_csrf(self):
        data = {'token': uuid.uuid4(), 'name': 'Pilot', 'scope': 'sentences', 'sampling': 'random', 'size': 30}
        address = url('evaluation-home', self.dictionary.pk)
        self.assertEqual(self.client.post(address, data).status_code, 404)
        self.assertEqual(self.visitor.get(address).status_code, 404)
        self.assertEqual(self.guest.get(address).status_code, 302)
        csrf = Client(enforce_csrf_checks=True); csrf.force_login(self.owner)
        self.assertEqual(csrf.post(address, data).status_code, 403)
        for _ in range(2):
            self.assertEqual(self.owner_client.post(address, data).status_code, 302)
        self.assertEqual(EvaluationSet.objects.count(), 1)
        self.assertContains(self.owner_client.get(address), url('settings', self.dictionary.pk))

    def test_random_sample_reproducible_and_accepted_only(self):
        for i in range(5):
            self.make_entry(f'Sentence {i}', f'Translation {i}', audio=False)
        pending = Entry.objects.create(dictionary=self.dictionary, created_by=self.owner, entry_type='sentence', word='DRAFT-SECRET')
        Contribution.objects.create(entry=pending, author=self.owner, kind='text', text_field='word', word='DRAFT-SECRET')
        batch = self.batch(sampling='random', size=3)
        expected = random.Random(batch.seed).sample(batch.population_ids, 3)
        self.assertEqual(list(batch.items.values_list('entry_id', flat=True)), expected)
        self.assertEqual(len(batch.population_ids), 6)
        self.assertNotIn(pending.pk, batch.population_ids)
        self.assertEqual(batch.language, 'Swedish')

    def test_shared_words_deduplicated_by_sense_not_spelling(self):
        sentence = self.make_entry('En annan katt.', 'Another cat.')
        self.link(sentence, self.word, 'katt')
        other_sense = self.make_entry('katt', 'different sense', kind='word', image=False)
        self.link(sentence, other_sense, 'katt')
        batch = self.batch()
        self.assertEqual(batch.units.filter(dimension='word_audio').count(), 2)
        self.assertEqual(batch.units.filter(dimension='word_translation').count(), 2)
        self.assertEqual(batch.units.filter(dimension='language').count(), 2)

    def test_standalone_words_and_no_audio_or_translation(self):
        entry = self.make_entry('hund', '', kind='word', image=False, audio=False)
        batch = self.batch(scope='words')
        missing = batch.units.filter(item__entry=entry)
        self.assertEqual(missing.count(), 2)
        self.assertTrue(all(u.missing for u in missing))
        self.assertEqual(set(batch.units.values_list('dimension', flat=True)), {'word_audio', 'word_translation'})
        self.start(batch)
        response = self.client.get(self.item_url(batch, batch.items.get(entry=entry)))
        self.assertContains(response, 'Missing material at sampling')

    def test_start_gates_competence_consent_and_freezes_profile(self):
        batch = self.batch()
        address = url('evaluation-set', self.dictionary.pk, batch.pk)
        self.skills(self.member, listening=0)
        self.assertEqual(self.client.post(address, {'dimensions': ['sentence_audio'], 'involvement': 'no', 'consent': 'on'}).status_code, 200)
        self.assertEqual(EvaluationSession.objects.count(), 0)
        self.assertEqual(self.client.post(address, {'dimensions': ['language'], 'involvement': 'no'}).status_code, 200)
        self.assertEqual(EvaluationSession.objects.count(), 0)
        data = {'dimensions': ['language'], 'involvement': 'yes', 'consent': 'on', 'evaluator_kind': 'ai'}
        for _ in range(2):
            self.assertEqual(self.client.post(address, data).status_code, 302)
        attempt = EvaluationSession.objects.get()
        self.assertEqual(attempt.evaluator_kind, 'human')
        self.skills(self.member, listening=3)
        attempt.refresh_from_db()
        self.assertEqual(attempt.competences['target']['listening'], 0)

    def test_save_next_resume_skip_revisit_and_no_default_rating(self):
        self.make_entry('Nästa mening.', 'Next sentence.')
        batch = self.batch(); attempt = self.start(batch)
        first, second = list(batch.items.all())
        response = self.client.get(self.item_url(batch, first))
        self.assertContains(response, 'Choose a judgement…')
        self.assertContains(response, 'Save and next')
        self.assertContains(response, 'formnovalidate')
        self.assertContains(response, 'Katten ligger på soffan.')
        self.assertEqual(EvaluationRating.objects.count(), 0)
        data = self.save_data(first)
        response = self.client.post(self.item_url(batch, first), data, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Nästa mening.')
        count = first.units.filter(missing=False).count()
        self.assertEqual(attempt.ratings.count(), count)
        response = self.client.post(self.item_url(batch, second), {'action': 'skip', 'revision': 0})
        self.assertEqual(response.status_code, 302)
        self.assertTrue(attempt.progress.get(item=second).skipped)
        response = self.client.get(url('evaluation-session', self.dictionary.pk, batch.pk))
        self.assertContains(response, 'You have reached the end')
        self.assertContains(response, 'Skipped')
        self.assertEqual(self.client.post(self.item_url(batch, first), data).status_code, 409)
        self.assertEqual(attempt.ratings.count(), count)
        response = self.client.post(self.item_url(batch, second), self.save_data(second, revision=1))
        self.assertEqual(response.status_code, 302)
        self.assertFalse(attempt.progress.get(item=second).skipped)

    def test_each_question_shows_its_own_material_before_the_rating(self):
        sofa = self.make_entry('soffa', 'sofa', kind='word', image=False)
        self.link(self.sentence, sofa, 'soffan')
        batch = self.batch(); self.start(batch)
        item = batch.items.first()
        html = self.client.get(self.item_url(batch)).content.decode()
        panels = re.findall(r'<fieldset[^>]*data-evaluation-dimension="([^"]+)"[^>]*>(.*?)</fieldset>', html, re.S)
        self.assertEqual(len(panels), 9)
        for dimension, panel in panels:
            material, question = panel.split('<select', 1)
            self.assertIn('Katten ligger på soffan.', material)
            self.assertIn('Choose a judgement', question)
            if dimension in {'image', 'translation', 'vocabulary', 'word_translation'}:
                self.assertIn(url('evaluation-media', self.dictionary.pk, batch.pk, item.pk, item.snapshot['entry']['image']['id']), material)
            if dimension == 'translation':
                self.assertIn('The cat is on the sofa.', material)
            if dimension == 'vocabulary':
                for value in ['katt', 'Katten', 'cat', 'soffa', 'soffan', 'sofa']:
                    self.assertIn(value, material)
                self.assertIn('Check the complete list', material)
            if dimension == 'sentence_audio':
                self.assertIn(url('evaluation-media', self.dictionary.pk, batch.pk, item.pk, item.snapshot['entry']['audio']['id']), material)
            if dimension.startswith('word_'):
                word = next(w for w in item.snapshot['words'] if '>' + w['text'] + '</strong>' in material)
                if dimension == 'word_translation':
                    self.assertIn(word['meaning'], material)
                else:
                    self.assertIn(url('evaluation-media', self.dictionary.pk, batch.pk, item.pk, word['audio']['id']), material)

    def test_both_skills_for_both_languages_and_saved_session_summary(self):
        batch = self.batch()
        address = url('evaluation-set', self.dictionary.pk, batch.pk)
        response = self.client.get(address)
        self.assertContains(response, 'Fluent / highly proficient', count=4)
        self.assertContains(response, 'Listening:', count=2)
        self.assertContains(response, 'Reading:', count=2)
        self.start(batch)
        self.skills(self.member, reading=1, listening=0, explanation=2)
        for page in [address, url('evaluation-session', self.dictionary.pk, batch.pk)]:
            response = self.client.get(page)
            self.assertContains(response, 'Language competences saved for this evaluation')
            self.assertContains(response, 'Fluent / highly proficient', count=4)
        new_batch = self.batch()
        response = self.client.get(url('evaluation-set', self.dictionary.pk, new_batch.pk))
        self.assertContains(response, 'Some knowledge', count=1)
        self.assertContains(response, 'Not able to assess', count=1)
        self.assertContains(response, 'Confident enough to assess', count=2)

    def test_missing_competence_is_displayed_as_not_declared(self):
        LanguageCompetence.objects.filter(user=self.member, language_key='english').delete()
        batch = self.batch()
        response = self.client.get(url('evaluation-set', self.dictionary.pk, batch.pk))
        self.assertContains(response, 'Not declared', count=2)
        self.assertContains(response, 'English')
        self.assertContains(response, 'Fluent / highly proficient', count=2)

    def test_incomplete_form_does_not_record_partial_ratings(self):
        batch = self.batch(); attempt = self.start(batch)
        record = batch.items.first(); data = self.save_data(record)
        del data[f'score_{record.units.filter(missing=False).first().pk}']
        response = self.client.post(self.item_url(batch), data)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(attempt.ratings.count(), 0)
        self.assertEqual(attempt.progress.count(), 0)

    def test_cannot_judge_excluded_and_missing_separately_counted(self):
        self.sentence.contributions.filter(kind='audio').update(status='removed')
        batch = self.batch(); self.start(batch)
        record = batch.items.first()
        self.client.post(self.item_url(batch), self.save_data(record, score='cannot'))
        data = ev.result_data(batch)
        audio = next(r for r in data['rows'] if r['dimension'] == 'sentence_audio')
        language = next(r for r in data['rows'] if r['dimension'] == 'language')
        self.assertEqual((audio['missing'], audio['scored']), (1, 0))
        self.assertEqual((language['cannot'], language['scored'], language['acceptable_percent']), (1, 0, None))

    def test_ratings_blinded_until_closed_and_owner_only_results(self):
        batch = self.batch(); attempt = self.start(batch)
        record = batch.items.first(); data = self.save_data(record, score='major')
        data[f'comment_{record.units.first().pk}'] = 'PRIVATE-RATING-COMMENT'
        self.client.post(self.item_url(batch), data)
        self.start(batch, self.owner)
        self.assertNotContains(self.owner_client.get(self.item_url(batch)), 'PRIVATE-RATING-COMMENT')
        for name in ['evaluation-results', 'evaluation-export']:
            self.assertEqual(self.owner_client.get(url(name, self.dictionary.pk, batch.pk)).status_code, 409)
        self.assertEqual(self.client.post(url('evaluation-close', self.dictionary.pk, batch.pk), {'confirm': 'yes'}).status_code, 404)
        self.assertEqual(self.owner_client.get(url('evaluation-close', self.dictionary.pk, batch.pk)).status_code, 200)
        batch.refresh_from_db(); self.assertIsNone(batch.closed_at)
        self.assertEqual(self.close(batch).status_code, 302)
        self.assertEqual(self.close(batch).status_code, 302)
        self.assertContains(self.owner_client.get(url('evaluation-results', self.dictionary.pk, batch.pk)), 'PRIVATE-RATING-COMMENT')
        self.assertEqual(self.client.get(url('evaluation-results', self.dictionary.pk, batch.pk)).status_code, 404)
        self.assertEqual(self.client.post(self.item_url(batch), self.save_data(record, revision=1)).status_code, 409)
        self.assertEqual(self.client.post(url('evaluation-set', self.dictionary.pk, batch.pk), {}).status_code, 409)
        self.assertEqual(attempt.ratings.count(), record.units.filter(missing=False).count())

    def test_edit_retains_old_scores_but_blocks_new_ratings(self):
        batch = self.batch(); self.start(batch)
        record = batch.items.first()
        self.client.post(self.item_url(batch), self.save_data(record))
        text = Contribution.objects.create(entry=self.sentence, author=self.owner, kind='text', text_field='word',
            word='Katten sitter på stolen.', base_version=self.sentence.text_version)
        accept(text, self.owner)
        self.assertEqual(self.client.get(self.item_url(batch)).status_code, 409)
        data = ev.result_data(batch)
        self.assertEqual(data['changed'], 1)
        self.assertEqual(data['excluded'], 0)
        self.assertGreater(len(data['ratings']), 0)
        self.assertEqual(record.snapshot['entry']['text'], 'Katten ligger på soffan.')
        self.close(batch)
        self.assertContains(self.owner_client.get(url('evaluation-results', self.dictionary.pk, batch.pk)), 'original sampled version')

    def test_word_link_or_audio_change_invalidates_page(self):
        batch = self.batch(); self.start(batch)
        SentenceWord.objects.filter(sentence_text=self.sentence.current_text).update(surface='changed')
        self.assertEqual(self.client.get(self.item_url(batch)).status_code, 409)
        SentenceWord.objects.filter(sentence_text=self.sentence.current_text).update(surface='Katten')
        self.assertEqual(self.client.get(self.item_url(batch)).status_code, 200)
        c = Contribution.objects.create(entry=self.word, author=self.owner, kind='audio',
            **write_upload(prepare_upload(recording(), 'audio'), self.dictionary.pk, []))
        accept(c, self.owner)
        self.assertEqual(self.client.get(self.item_url(batch)).status_code, 409)

    def test_withdrawn_source_blocks_snapshot_media_summary_and_export(self):
        batch = self.batch(); self.start(batch)
        record = batch.items.first(); data = self.save_data(record)
        data[f'comment_{record.units.first().pk}'] = 'SENSITIVE-COMMENT'
        self.client.post(self.item_url(batch), data)
        image = record.snapshot['entry']['image']
        media = url('evaluation-media', self.dictionary.pk, batch.pk, record.pk, image['id'])
        response = self.client.get(media)
        self.assertEqual(response.status_code, 200); response.close()
        Contribution.objects.filter(pk=image['id']).update(status='withdrawn')
        self.assertEqual(self.client.get(self.item_url(batch)).status_code, 404)
        self.assertEqual(self.client.get(media).status_code, 404)
        self.close(batch)
        for name in ['evaluation-results', 'evaluation-export']:
            response = self.owner_client.get(url(name, self.dictionary.pk, batch.pk))
            self.assertEqual(response.status_code, 200)
            self.assertNotContains(response, 'SENSITIVE-COMMENT')
            self.assertNotContains(response, self.sentence.word)
        self.assertEqual(ev.result_data(batch)['excluded'], 1)

    def test_source_moved_to_collection_and_withdrawal_hold_are_blocked(self):
        batch = self.batch(); self.start(batch)
        record = batch.items.first(); image_id = record.snapshot['entry']['image']['id']
        state = Participation.objects.create(user=self.owner, dictionary=self.dictionary, withdrawn=False)
        WithdrawalHold.objects.create(participation=state, contribution_id=image_id)
        self.assertEqual(self.client.get(self.item_url(batch)).status_code, 404)
        WithdrawalHold.objects.all().delete()
        private = Dictionary.objects.create(owner=self.owner, name='private', personal=True, language='Swedish')
        entry = Entry.objects.create(dictionary=private, created_by=self.owner)
        Contribution.objects.filter(pk=image_id).update(entry=entry)
        self.assertEqual(self.client.get(self.item_url(batch)).status_code, 404)

    def test_withdrawn_evaluator_cannot_use_public_visitor_fallback(self):
        self.dictionary.public_browsing_enabled = True; self.dictionary.save()
        batch = self.batch(allow_visitors=True); self.start(batch)
        Participation.objects.create(user=self.member, dictionary=self.dictionary, withdrawn=True)
        for address in [url('evaluation-home', self.dictionary.pk), url('evaluation-set', self.dictionary.pk, batch.pk),
                        self.item_url(batch)]:
            self.assertEqual(self.client.get(address).status_code, 404)

    def test_inactive_members_and_other_dictionary_ids_denied(self):
        batch = self.batch(); self.start(batch)
        Membership.objects.filter(user=self.member, dictionary=self.dictionary).update(status='inactive')
        self.assertEqual(self.client.get(self.item_url(batch)).status_code, 404)
        other = Dictionary.objects.create(owner=self.member, name='Other', language='Swedish')
        self.assertEqual(self.client.get(url('evaluation-set', other.pk, batch.pk)).status_code, 404)
        self.assertEqual(self.client.get(url('evaluation-item', other.pk, batch.pk, batch.items.first().pk)).status_code, 404)

    def test_visitors_explicit_opt_in_public_access_and_no_anonymous_writes(self):
        batch = self.batch()
        self.assertEqual(self.visitor.get(url('evaluation-set', self.dictionary.pk, batch.pk)).status_code, 404)
        self.dictionary.public_browsing_enabled = True; self.dictionary.save()
        self.assertEqual(self.visitor.get(url('evaluation-set', self.dictionary.pk, batch.pk)).status_code, 404)
        batch.allow_visitors = True; batch.save()
        self.assertEqual(self.visitor.get(url('evaluation-set', self.dictionary.pk, batch.pk)).status_code, 200)
        self.assertContains(self.guest.get(url('public-dictionary', self.dictionary.pk)), 'Evaluate')
        self.assertEqual(self.guest.post(url('evaluation-set', self.dictionary.pk, batch.pk), {}).status_code, 302)
        self.start(batch, self.outsider)
        self.assertEqual(self.visitor.get(self.item_url(batch)).status_code, 200)
        Dictionary.objects.filter(pk=self.dictionary.pk).update(public_browsing_enabled=False)
        self.assertEqual(self.visitor.get(self.item_url(batch)).status_code, 404)
        self.assertEqual(self.client.get(url('evaluation-set', self.dictionary.pk, batch.pk)).status_code, 200)

    def test_visitor_media_cannot_retrieve_superseded_snapshot(self):
        self.dictionary.public_browsing_enabled = True; self.dictionary.save()
        batch = self.batch(allow_visitors=True); self.start(batch, self.outsider)
        record = batch.items.first(); image = record.snapshot['entry']['image']
        media = url('evaluation-media', self.dictionary.pk, batch.pk, record.pk, image['id'])
        response = self.visitor.get(media); self.assertEqual(response.status_code, 200); response.close()
        SentenceWord.objects.filter(sentence_text=self.sentence.current_text).delete()
        self.assertEqual(self.visitor.get(media).status_code, 404)

    def test_media_scoped_and_range_served_without_windows_handle_leaks(self):
        batch = self.batch(); self.start(batch)
        record = batch.items.first(); clip = record.snapshot['entry']['audio']
        media = url('evaluation-media', self.dictionary.pk, batch.pk, record.pk, clip['id'])
        response = self.client.get(media, HTTP_RANGE='bytes=0-15')
        self.assertEqual(response.status_code, 206)
        self.assertEqual(len(b''.join(response.streaming_content)), 16); response.close()
        other = self.make_entry('Secret', 'Other page')
        self.assertEqual(self.client.get(url('evaluation-media', self.dictionary.pk, batch.pk, record.pk, other.selected_image_id)).status_code, 404)
        self.assertEqual(self.visitor.get(media).status_code, 404)
        self.assertEqual(self.guest.get(media).status_code, 302)

    def test_stats_count_overlapping_units_and_csv_safe_private(self):
        batch = self.batch()
        for user, score in [(self.member, 'ok'), (self.third, 'major')]:
            attempt = self.start(batch, user)
            for unit in batch.units.filter(missing=False):
                EvaluationRating.objects.create(session=attempt, unit=unit, score=score,
                    comment='=DANGEROUS()' if user == self.member else '<script>example</script>')
        self.close(batch)
        data = ev.result_data(batch)
        row = next(r for r in data['rows'] if r['dimension'] == 'language')
        self.assertEqual((row['ok'], row['major'], row['acceptable_percent']), (1, 1, 50))
        self.assertEqual((row['pairs'], row['overlap_units'], row['exact_percent']), (1, 1, 0))
        response = self.owner_client.get(url('evaluation-results', self.dictionary.pk, batch.pk))
        self.assertContains(response, '&lt;script&gt;example&lt;/script&gt;')
        self.assertNotContains(response, '<script>example</script>')
        response = self.owner_client.get(url('evaluation-export', self.dictionary.pk, batch.pk))
        self.assertIn('no-store', response['Cache-Control'])
        rows = list(csv.DictReader(io.StringIO(response.content.decode())))
        self.assertEqual({r['evaluator'] for r in rows}, {'R1', 'R2'})
        self.assertIn("'=DANGEROUS()", {r['comment'] for r in rows})
        self.assertNotContains(response, self.member.username)
        self.assertNotContains(response, '.wav')

    def test_missing_and_unrated_units_are_in_csv(self):
        self.sentence.contributions.filter(kind='audio').update(status='removed')
        batch = self.batch(); self.close(batch)
        response = self.owner_client.get(url('evaluation-export', self.dictionary.pk, batch.pk))
        rows = list(csv.DictReader(io.StringIO(response.content.decode())))
        self.assertTrue(any(r['dimension'] == 'sentence_audio' and r['missing_material'] == 'True' for r in rows))
        self.assertTrue(all(r['score'] == '' for r in rows))

    def test_no_ai_calls_and_bounded_graph_queries(self):
        for i in range(10):
            entry = self.make_entry(f'Sentence {i}', f'Translation {i}', audio=False)
            self.link(entry, self.word, 'katt')
        with patch('projects.views._build_ai_client', side_effect=AssertionError('Evaluation must not call AI')):
            with CaptureQueriesContext(connection) as captured:
                live = ev.graph(self.dictionary)
            self.assertLessEqual(len(captured), 5)
            self.assertEqual(len(live), 12)
            batch = self.batch(); self.start(batch)
            with CaptureQueriesContext(connection) as captured:
                response = self.client.get(self.item_url(batch))
            self.assertEqual(response.status_code, 200)
            self.assertLess(len(captured), 40)

    def test_no_get_mutation_no_cache_and_post_csrf(self):
        batch = self.batch(); self.start(batch)
        record = batch.items.first()
        for address in [url('evaluation-home', self.dictionary.pk), url('evaluation-set', self.dictionary.pk, batch.pk),
                        url('evaluation-session', self.dictionary.pk, batch.pk), self.item_url(batch)]:
            response = self.client.get(address)
            self.assertEqual(response.status_code, 200)
            self.assertIn('no-store', response['Cache-Control'])
        self.assertEqual(EvaluationRating.objects.count(), 0)
        csrf = Client(enforce_csrf_checks=True); csrf.force_login(self.member)
        self.assertEqual(csrf.post(self.item_url(batch), self.save_data(record)).status_code, 403)
        self.assertEqual(self.client.delete(self.item_url(batch)).status_code, 405)

    def test_departed_evaluators_ratings_are_withheld(self):
        batch = self.batch(); attempt = self.start(batch)
        self.client.post(self.item_url(batch), self.save_data(batch.items.first()))
        self.assertTrue(ev.result_data(batch)['ratings'])
        Participation.objects.create(user=self.member, dictionary=self.dictionary, withdrawn=True)
        self.assertEqual(ev.result_data(batch)['ratings'], [])
        self.assertGreater(attempt.ratings.count(), 0)

    def test_nonhuman_records_never_enter_human_statistics(self):
        batch = self.batch(); attempt = self.start(batch)
        attempt.evaluator_kind = 'ai'; attempt.save()
        for unit in batch.units.filter(missing=False):
            EvaluationRating.objects.create(session=attempt, unit=unit, score='major')
        self.assertEqual(ev.result_data(batch)['ratings'], [])
        self.assertEqual(self.client.get(self.item_url(batch)).status_code, 404)

    def test_summary_queries_do_not_grow_per_rating(self):
        for i in range(12):
            sentence = self.make_entry(f'Sentence {i}', f'Translation {i}', audio=False)
            self.link(sentence, self.word, 'katt')
        batch = self.batch()
        for user in [self.member, self.third]:
            attempt = self.start(batch, user)
            EvaluationRating.objects.bulk_create([EvaluationRating(session=attempt, unit=u, score='ok')
                for u in batch.units.filter(missing=False)])
        with CaptureQueriesContext(connection) as captured:
            data = ev.result_data(batch)
        self.assertLessEqual(len(captured), 12)
        self.assertEqual(data['sample_count'], 13)
        word_audio = next(r for r in data['rows'] if r['dimension'] == 'word_audio')
        self.assertEqual((word_audio['units'], word_audio['scored']), (1, 2))

    def test_empty_sample_rejected_and_visitor_setting_needs_public(self):
        with self.assertRaises(Conflict):
            self.batch(allow_visitors=True)
        self.sentence.archived = True; self.sentence.save()
        with self.assertRaises(Conflict):
            self.batch()


class AgreementTests(SimpleTestCase):
    def test_perfect_with_variation(self):
        result = ev.agreement([['ok', 'ok'], ['minor', 'minor'], ['major', 'major']])
        self.assertEqual((result['alpha'], result['exact_percent'], result['pairs']), (1, 100, 3))

    def test_ordinal_worked_example(self):
        # Marginals (3,1,2); ordinal squared distances 4,12.25,2.25.
        # Do=4/3 and De=6, so alpha=7/9.
        result = ev.agreement([['ok', 'ok'], ['ok', 'minor'], ['major', 'major']])
        self.assertAlmostEqual(result['alpha'], 7 / 9)
        self.assertAlmostEqual(result['exact_percent'], 200 / 3)

    def test_disagreement_can_be_negative(self):
        self.assertAlmostEqual(ev.agreement([['ok', 'major'], ['major', 'ok']])['alpha'], -.5)

    def test_abstentions_singletons_and_constant_ratings(self):
        self.assertIsNone(ev.agreement([['ok', 'cannot'], ['major']])['alpha'])
        result = ev.agreement([['ok', 'ok'], ['ok', 'ok', 'cannot']])
        self.assertEqual(result['exact_percent'], 100)
        self.assertIsNone(result['alpha'])
        self.assertIn('No variation', result['reason'])

    def test_unequal_raters_coincidence_weighting(self):
        # Three ratings (0,0,1), two (1,1): N=5, marginals(2,3).
        # Do=1, De=1.5 in nominal-distance units, alpha=1/3;
        # the sole ordinal distance cancels.
        result = ev.agreement([['ok', 'ok', 'minor'], ['minor', 'minor']])
        self.assertAlmostEqual(result['alpha'], 1 / 3)
        self.assertEqual(result['pairs'], 4)
        self.assertEqual(result['overlap_units'], 2)
        self.assertEqual(result['exact_percent'], 50)

    def test_csv_formula_neutralisation(self):
        for value in ['=SUM(1)', '+1', '-1', '@x', '  =x', '\t=1']:
            self.assertTrue(csv_cell(value).startswith("'"))
        self.assertEqual(csv_cell('ordinary text'), 'ordinary text')
