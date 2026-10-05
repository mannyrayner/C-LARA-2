"""Sequential, private review and durable attention notes; no provider calls."""
from unittest.mock import patch

from django.test import TestCase, Client, override_settings

from community_dictionary.models import PortEntryLink, PortItem
from community_dictionary.participation import withdraw_all
from community_dictionary.services import add_contributions
from .test_porting import PortingTests, response


@override_settings(OPENAI_API_KEY='fixture-only', CREDITS_ENABLED=True,
    COMMUNITY_DICTIONARY_PHOTO_MODEL='gpt-6-sol', COMMUNITY_DICTIONARY_PORT_WINDOW=2)
class PortReviewTests(TestCase):
    setUp = PortingTests.setUp
    url = PortingTests.url
    post = PortingTests.post
    create_entry = PortingTests.create_entry
    seed = PortingTests.seed
    quote = PortingTests.quote
    approve = PortingTests.approve
    process = PortingTests.process
    save = PortingTests.save

    def ready(self, words=('katt','hund'), author=None):
        for word in words:
            self.seed(word, author=author)
        run = self.approve(self.quote())
        for item in run.items.all():
            self.process(item, response('gatto' if item.source_entry.word == 'katt' else 'cane'))
        return run, list(run.items.all())

    def review_url(self, item):
        return self.url('port-review', item.run_id, item.pk)

    def values(self, item, **extra):
        return {key:item.result[key] for key in ['word','meaning','category']} | extra

    def test_save_moves_to_next_and_final_list_shows_actual_word(self):
        run, (a,b) = self.ready()
        result = self.client.post(self.review_url(a), self.values(a, word='il gatto'))
        self.assertRedirects(result, self.review_url(b))
        page = self.client.get(self.url('port-run',run.pk))
        self.assertContains(page,'il gatto · saved')
        self.assertContains(page,'Open saved entry')
        self.assertNotContains(page,f'Entry {a.source_entry_id} · saved')
        result = self.client.post(self.review_url(b), self.values(b))
        self.assertRedirects(result,self.url('port-run',run.pk))
        self.assertContains(self.client.get(self.url('port-run',run.pk)),'cane · saved')
        # Duplicate submission must not save the next item or overwrite anything.
        self.client.post(self.review_url(a), self.values(a,word='wrong'))
        self.assertEqual(PortEntryLink.objects.get(source=a.source_entry).destination.word,'il gatto')

    def test_next_crosses_pagination_boundary(self):
        for number in range(21):
            self.seed('word'+str(number))
        run = self.approve(self.quote())
        items = list(run.items.all())
        run.items.filter(pk__in=[i.pk for i in items[:19]]).update(status='saved')
        run.items.filter(pk__in=[i.pk for i in items[19:]]).update(status='queued')
        self.process(items[19]); self.process(items[20])
        result = self.client.post(self.review_url(items[19]), self.values(items[19]))
        self.assertRedirects(result,self.review_url(items[20]))

    def test_flag_keeps_edits_without_accepting_or_regenerating(self):
        run, (a,b) = self.ready()
        with patch('community_dictionary.port_ai.translate') as translate, patch('community_dictionary.tts.synthesize') as synthesize:
            result = self.client.post(self.review_url(a), self.values(a, action='flag',
                word='il gatto', category='', attention_note='Listen again'))
        self.assertRedirects(result,self.review_url(b))
        self.assertFalse(translate.called); self.assertFalse(synthesize.called)
        a.refresh_from_db()
        self.assertTrue(a.needs_attention); self.assertEqual(a.status,'ready')
        self.assertEqual(a.review_values['word'],'il gatto')
        self.assertEqual(a.review_values['category'],'')
        self.assertEqual(a.result['word'],'gatto')
        self.assertFalse(PortEntryLink.objects.exists())
        page = self.client.get(self.review_url(a)+'?attention=1')
        self.assertContains(page,'value="il gatto"')
        self.assertEqual(page.context['form']['category'].value(),'')
        self.assertContains(page,'Listen again')
        # Saving the other item should not immediately recycle the set-aside one.
        result = self.client.post(self.review_url(b), self.values(b))
        self.assertRedirects(result,self.url('port-run',run.pk))
        flagged = self.client.get(self.url('port-run',run.pk)+'?attention=1')
        self.assertContains(flagged,'Listen again')
        self.assertEqual([i.pk for i in flagged.context['page']],[a.pk])
        self.assertContains(flagged, self.review_url(a)+'?attention=1')

    def test_flag_allows_unresolved_blank_word_but_save_requires_word(self):
        run, (a,) = self.ready(('katt',))
        result = self.client.post(self.review_url(a),self.values(a,action='flag',word=''))
        self.assertRedirects(result,self.url('port-run',run.pk))
        a.refresh_from_db(); self.assertTrue(a.needs_attention)
        result = self.client.post(self.review_url(a),self.values(a,word=''))
        self.assertEqual(result.status_code,200)
        self.assertTrue(result.context['form'].errors)
        self.assertFalse(PortEntryLink.objects.exists())

    def test_attention_review_stays_in_filter_and_can_save_with_or_without_flag(self):
        run, (a,b,c) = self.ready(('katt','hund','häst'))
        run.items.filter(pk__in=[a.pk,c.pk]).update(needs_attention=True,attention_note='Pronunciation')
        result = self.client.post(self.review_url(a)+'?attention=1',self.values(a,
            needs_attention='on',attention_note='Still to check'))
        self.assertRedirects(result,self.review_url(c)+'?attention=1')
        a.refresh_from_db(); self.assertTrue(a.needs_attention)
        result = self.client.post(self.review_url(c)+'?attention=1',self.values(c))
        self.assertRedirects(result,self.url('port-run',run.pk)+'?attention=1')
        c.refresh_from_db(); self.assertFalse(c.needs_attention);self.assertEqual(c.attention_note,'')
        b.refresh_from_db(); self.assertEqual(b.status,'ready')

    def test_saved_flag_set_clear_idempotence_and_page_kept(self):
        run, (a,) = self.ready(('katt',))
        entry = self.save(a)
        url = self.url('port-attention',run.pk,a.pk)
        for _ in range(2):
            result=self.client.post(url+'?page=2',{'action':'flag','attention_note':'Audio too English'})
            self.assertEqual(result.url,self.url('port-run',run.pk)+'?page=2')
        a.refresh_from_db(); self.assertTrue(a.needs_attention)
        page=self.client.get(self.url('port-run',run.pk)+'?attention=1')
        self.assertContains(page,'Audio too English');self.assertContains(page,'Mark as resolved')
        add_contributions(entry,self.owner,{'word':'il gatto','edit_text':True},[],publish=True)
        self.assertContains(self.client.get(self.url('port-run',run.pk)),'il gatto · saved')
        for _ in range(2):
            self.client.post(url+'?attention=1',{'action':'clear'})
        a.refresh_from_db(); self.assertFalse(a.needs_attention);self.assertEqual(a.attention_note,'')
        self.assertContains(self.client.get(self.url('port-run',run.pk)+'?attention=1'),'No items are flagged')

    def test_withdrawal_clears_drafts_notes_and_hides_saved_labels(self):
        run, (a,b) = self.ready(author=self.member)
        self.client.post(self.review_url(a),self.values(a,action='flag',word='secret draft',attention_note='secret note'))
        self.save(b)
        self.client.post(self.url('port-attention',run.pk,b.pk),{'action':'flag','attention_note':'secret saved note'})
        with self.captureOnCommitCallbacks(execute=True):
            withdraw_all(self.member,self.dictionary.pk,0)
        a.refresh_from_db();b.refresh_from_db()
        self.assertEqual(a.review_values,{}); self.assertEqual(a.attention_note,'')
        self.assertFalse(b.needs_attention); self.assertEqual(b.attention_note,'')
        page=self.client.get(self.url('port-run',run.pk))
        self.assertNotContains(page,'secret');self.assertNotContains(page,'cane · saved')
        self.assertEqual(self.client.post(self.url('port-attention',run.pk,b.pk),{'action':'flag'}).status_code,409)

    def test_next_skips_stale_preview_and_wrapped_order_is_deterministic(self):
        run, (a,b,c) = self.ready(('katt','hund','häst'))
        PortItem.objects.filter(pk=b.pk).update(destination_digest='stale')
        # Starting at c wraps to a; saving a then skips stale b.
        self.assertRedirects(self.client.post(self.review_url(c),self.values(c)),self.review_url(a))
        self.assertRedirects(self.client.post(self.review_url(a),self.values(a)),self.url('port-run',run.pk))

    def test_flag_permission_csrf_method_and_scope_boundaries(self):
        run,(a,)=self.ready(('katt',)); self.save(a)
        url=self.url('port-attention',run.pk,a.pk)
        self.assertEqual(self.client.get(url).status_code,405)
        client=Client(enforce_csrf_checks=True);client.force_login(self.owner)
        self.assertEqual(client.post(url,{'action':'flag'}).status_code,403)
        for user in [self.member,self.outsider]:
            self.client.force_login(user)
            self.assertEqual(self.client.post(url,{'action':'flag'}).status_code,404)
        self.client.force_login(self.owner)
        bad=url.replace(f'/{self.dictionary.pk}/language-port/', '/999/language-port/')
        self.assertEqual(self.client.post(bad,{'action':'flag'}).status_code,404)
        self.assertEqual(self.client.post(url,{'action':'toggle'}).status_code,400)
        self.assertEqual(self.client.post(url,{'action':'flag','attention_note':'x'*501}).status_code,400)
        a.refresh_from_db();self.assertFalse(a.needs_attention)

    def test_annotations_and_saved_words_are_html_escaped(self):
        run,(a,)=self.ready(('katt',))
        result=self.client.post(self.review_url(a),self.values(a,word='<script>bad()</script>',
            needs_attention='on',attention_note='<script>note()</script>'),follow=True)
        self.assertContains(result,'&lt;script&gt;bad()&lt;/script&gt;')
        self.assertNotContains(result,'<script>bad()')
        self.assertNotContains(result,'<script>note()')
        self.assertContains(result,'&lt;script&gt;note()&lt;/script&gt;')
        self.assertEqual(result.headers['Cache-Control'],'private, no-store')

    def test_older_run_results_remain_accessible_from_version(self):
        run,(a,)=self.ready(('katt',));self.save(a)
        self.quote(port=run.port)
        page=self.client.get(self.url('port-update',run.port_id))
        self.assertContains(page,'Previous results')
        self.assertContains(page,self.url('port-run',run.pk)+'?attention=1')
