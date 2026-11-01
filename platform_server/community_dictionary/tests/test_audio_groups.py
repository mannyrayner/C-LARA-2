"""Grouped pronunciation review: scope, custody, cost and local audio reuse."""
import uuid
from unittest.mock import patch

from django.test import TestCase, override_settings
from community_dictionary import audio_review as review, sentence_forms as sf
from community_dictionary.collections import dependent_ids
from community_dictionary.models import Contribution, SentenceWord
from community_dictionary.participation import withdraw_all, restore_all
from community_dictionary.services import Conflict, add_contributions
from community_dictionary.storage import path_for
from projects.models import CreditLedgerEntry
from . import test_audio_review as review_fixtures


@override_settings(OPENAI_API_KEY='fixture-only', CREDITS_ENABLED=True,
    COMMUNITY_DICTIONARY_PORT_WINDOW=2, PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class GroupReviewTests(TestCase):
    setUp = review_fixtures.ReviewTests.setUp
    seed = review_fixtures.ReviewTests.seed
    old_audio = review_fixtures.ReviewTests.old_audio
    mark = review_fixtures.ReviewTests.mark
    approve = review_fixtures.ReviewTests.approve
    synthesis = staticmethod(review_fixtures.ReviewTests.synthesis)
    finish = review_fixtures.ReviewTests.finish
    choose = review_fixtures.ReviewTests.choose
    url = review_fixtures.ReviewTests.url

    def form(self, lemma, sentence='Le bonnet est vert.', meaning='is', surface='est', author=None):
        entry = self.seed(sentence, 'Sentence translation', kind='sentence', author=author)
        link = SentenceWord.objects.create(sentence_text=entry.current_text,
            word_entry=lemma, word_text=lemma.current_text, surface=surface)
        return sf.publish(link, meaning, author or self.owner, {'origin':'synthetic'})

    def pair(self):
        lemma = self.seed('être', 'be')
        first = self.form(lemma)
        second = self.form(lemma, 'Le ciel est rose au-dessus des maisons.', 'is (a colour)')
        return first, second

    def audio_group(self, part):
        return next(g for g in review.review_groups(self.owner, self.dictionary, include_expressions=True)
                    if any(r['id']==part.pk for r in g['members']))

    def mark_all(self, part, decision='replace'):
        group = self.audio_group(part)
        review.mark_group(self.owner, self.dictionary, group['word']['id'], group['token'], decision)

    def test_default_excludes_phrases_and_quote_respects_filter(self):
        words = [self.seed(word) for word in ('court', 'queue', 'de l’autre côté', 'déguisée en', 'en forme de lapin')]
        for entry in words:
            self.old_audio(entry); self.mark(entry.current_text)
        response = self.client.get(self.url())
        self.assertEqual(response.context['total'], 2)
        for entry in words[2:]:self.assertNotContains(response, entry.word)
        self.assertContains(response, 'Include expressions containing homographs')
        response = self.client.get(self.url()+'?expressions=1')
        self.assertEqual(response.context['total'], 5)
        narrow = review.quote(self.owner, self.dictionary, uuid.uuid4(), 1)
        broad = review.quote(self.owner, self.dictionary, uuid.uuid4(), 1, include_expressions=True)
        self.assertEqual(narrow.items.count(), 2); self.assertEqual(broad.items.count(), 5)
        self.assertFalse(CreditLedgerEntry.objects.exists())

    def test_same_lemma_forms_group_but_other_senses_voices_and_human_audio_do_not(self):
        first, second = self.pair()
        self.old_audio(first.entry, first); self.old_audio(second.entry, second)
        east = self.seed('est', 'east'); self.old_audio(east)
        another_sense = self.form(self.seed('être', 'exist'))
        other_voice = self.form(sf.current(first).word_entry, 'Il est là.')
        clip = self.old_audio(other_voice.entry, other_voice)
        clip.provenance['voice'] = 'coral'; clip.save()
        human = self.form(sf.current(first).word_entry, 'Il est ici.')
        self.old_audio(human.entry, human, human=True)
        group = self.audio_group(first)
        self.assertEqual([r['id'] for r in group['members']], [first.pk, second.pk])
        self.assertEqual(len(self.audio_group(another_sense)['members']), 1)
        self.assertEqual(len(self.audio_group(other_voice)['members']), 1)
        self.assertTrue(self.audio_group(human)['protected'])
        response = self.client.get(self.url())
        self.assertContains(response, '2 occurrences')
        self.assertContains(response, second.entry.word)
        self.assertContains(response, second.meaning)

    def test_group_candidates_charged_once_and_applied_to_each_occurrence(self):
        first, second = self.pair()
        before = [(p.pk,p.word,p.meaning,p.author_id,p.provenance) for p in (first,second)]
        old = [self.old_audio(p.entry,p) for p in (first,second)]
        self.mark_all(first)
        run = review.quote(self.owner, self.dictionary, uuid.uuid4(), 3)
        self.assertEqual(run.items.count(), 1)
        self.assertEqual(len(run.items.get().result['clips']), 3)
        self.assertEqual(len(run.items.get().snapshot['words']), 2)
        self.approve(run); _carrier, generated = self.finish(run)
        self.assertEqual(generated.call_count, 3)
        self.assertEqual(self.client.get(self.url('run', run.pk)).context['words'], 1)
        clip = self.choose(run, 1)
        self.assertEqual(len(clip['accepted_audio_ids']), 2)
        audio = [sf.audio(p) for p in (first,second)]
        self.assertNotEqual(audio[0].file_path, audio[1].file_path)
        self.assertEqual(path_for(audio[0].file_path).read_bytes(), path_for(audio[1].file_path).read_bytes())
        self.assertIn(audio[1].pk, dependent_ids([audio[0].pk]))
        for previous in old:
            previous.refresh_from_db(); self.assertEqual(previous.status, 'superseded')
            self.assertTrue(path_for(previous.file_path).exists())
        for part in (first,second):part.refresh_from_db()
        self.assertEqual(before, [(p.pk,p.word,p.meaning,p.author_id,p.provenance) for p in (first,second)])
        self.assertEqual(self.audio_group(first)['decision'], 'keep')
        response = self.client.get(self.url())
        est = next(g for g in response.context['rows'] if g['word']['word']=='est')
        self.assertEqual(len(est['recordings']), 1)
        with self.assertRaises(Conflict):self.choose(run, 0)

    def test_existing_recording_repair_is_free_preserves_attribution_and_withdraws(self):
        first, second = self.pair()
        source = self.old_audio(first.entry, first)
        source.author = self.member; source.controlled_by = self.member; source.save()
        old = self.old_audio(second.entry, second)
        group = self.audio_group(first)
        data = {'action':'reuse', 'part':group['word']['id'], 'token':group['token'], 'audio':source.pk}
        with patch('community_dictionary.tts.synthesize') as api:
            self.assertEqual(self.client.post(self.url(), data).status_code, 302)
        api.assert_not_called(); self.assertFalse(CreditLedgerEntry.objects.exists())
        copied = sf.audio(second)
        self.assertEqual((copied.author_id, copied.controlled_by_id), (self.member.pk,self.member.pk))
        self.assertEqual(copied.provenance['audio_copied_from'],source.pk)
        self.assertEqual(sf.audio(first).pk,source.pk)
        old.refresh_from_db(); self.assertEqual(old.status,'superseded')
        self.assertEqual(self.client.post(self.url(), data).status_code,409)
        withdraw_all(self.member,self.dictionary.pk,0)
        copied.refresh_from_db(); self.assertTrue(copied.entry.dictionary.personal)
        restore_all(self.member,self.dictionary.pk,1)
        copied.refresh_from_db(); self.assertEqual(copied.entry.dictionary_id,self.dictionary.pk)
        self.assertTrue(sf.audio_current(copied))

    def test_stale_group_addition_edit_and_human_recording_block_group_actions(self):
        first, second = self.pair()
        source = self.old_audio(first.entry,first); self.old_audio(second.entry,second)
        group = self.audio_group(first)
        third = self.form(sf.current(first).word_entry, 'Le chat est noir.')
        with self.assertRaises(Conflict):
            review.use_existing(self.owner,self.dictionary,group['word']['id'],group['token'],source.pk,[])
        self.mark_all(first)
        run = review.quote(self.owner,self.dictionary,uuid.uuid4(),1); self.approve(run); self.finish(run)
        self.old_audio(third.entry,third,human=True)
        with self.assertRaises(Conflict):self.choose(run)
        self.assertEqual(sf.audio(first).pk,source.pk)
        current = self.audio_group(first)
        add_contributions(second.entry,self.owner,{'word':'Le ciel devient rose.'},[],publish=True)
        with self.assertRaises(Conflict):
            review.mark_group(self.owner,self.dictionary,current['word']['id'],current['token'],'keep')

    def test_more_candidates_keep_group_scope_and_legacy_jobs_remain_single_occurrence(self):
        first, second = self.pair()
        self.mark_all(first)
        run = review.quote(self.owner,self.dictionary,uuid.uuid4(),1); self.approve(run); self.finish(run)
        item = run.items.get()
        more = review.quote_more(self.owner,self.dictionary,run.pk,item.pk,first.pk,uuid.uuid4(),2)
        self.assertEqual(len(more.items.get().snapshot['words']),2)
        self.assertEqual(len(more.items.get().result['clips']),2)
        # Old jobs did not promise multi-occurrence replacement.
        item.snapshot = {'words':[item.snapshot['words'][0]]}; item.save()
        self.choose(run)
        self.assertIsNotNone(sf.audio(first)); self.assertIsNone(sf.audio(second))

    def test_future_homograph_reuse_requires_approval_same_sense_voice_and_live_sources(self):
        first, second = self.pair()
        source = self.old_audio(first.entry,first)
        self.assertIsNone(sf.reuse_audio(second, 'marin', []))
        self.mark(first,'keep')
        self.assertIsNone(sf.reuse_audio(second, 'coral', []))
        wrong_sense = self.form(self.seed('être','exist'))
        self.assertIsNone(sf.reuse_audio(wrong_sense,'marin',[]))
        copied = sf.reuse_audio(second,'marin',[])
        self.assertEqual(copied.provenance['audio_copied_from'],source.pk)
        self.assertEqual(sf.reuse_audio(second,'marin',[]).pk,copied.pk)
        third = self.form(sf.current(first).word_entry,'Le chat est noir.')
        self.mark(first,'replace')
        self.assertIsNone(sf.reuse_audio(third,'marin',[]))
        self.mark(first,'keep')
        path_for(source.file_path).unlink()
        # The separately copied file is still usable, while its root remains visible.
        reused = sf.reuse_audio(third,'marin',[])
        self.assertEqual(reused.provenance['audio_copied_from'],copied.pk)
