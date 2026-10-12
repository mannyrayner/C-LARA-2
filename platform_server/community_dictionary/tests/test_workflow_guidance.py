"""Suggestions never spend on GET; one-click approval binds scope and cost."""
from decimal import Decimal
import time
from unittest.mock import patch

from django.core import signing
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from projects.models import CreditAccount, CreditLedgerEntry, Profile
from community_dictionary import workflow, porting, port_vocabulary
from community_dictionary.models import Dictionary, Membership, MembershipRequest, PortRun, LanguagePort, VocabularyState
from community_dictionary.services import add_contributions
from . import test_batch_descriptions as fixtures


@override_settings(OPENAI_API_KEY='fixture-only', CREDITS_ENABLED=False)
class WorkflowGuidanceTests(TestCase):
    setUp = fixtures.BatchDescriptionTests.setUp
    picture = fixtures.BatchDescriptionTests.picture
    create_entry = fixtures.BatchDescriptionTests.create_entry
    post = fixtures.BatchDescriptionTests.post
    url = fixtures.BatchDescriptionTests.url
    quote = fixtures.BatchDescriptionTests.quote
    approve = fixtures.BatchDescriptionTests.approve
    process = fixtures.BatchDescriptionTests.process
    save = fixtures.BatchDescriptionTests.save

    def step(self):
        self.dictionary.refresh_from_db()
        return workflow.suggestion(self.owner, self.dictionary, details=True)

    def start(self, token=None, client=None):
        return (client or self.client).post(self.url('workflow-start'), {'approval': token or self.step()['approval']})

    def test_read_only_offer_defaults_on_and_preserves_pending_hints(self):
        entry = self.picture(pending=True, meaning='cat')
        with patch('community_dictionary.batch_descriptions.interpret', side_effect=AssertionError('No API')):
            for _ in range(2):
                page = self.client.get(self.url('dictionary'))
                self.assertContains(page, '1 picture ready for sentences')
                self.assertContains(page, 'Rough API estimate')
                self.assertTrue(page.context['next_step']['approval'])
                self.assertContains(self.client.get(reverse('community_dictionary:home')), '1 picture ready for sentences')
        self.assertEqual(LanguagePort.objects.count(), 0)
        self.assertEqual(PortRun.objects.count(), 0)
        self.assertTrue(entry.contributions.filter(kind='image', status='pending').exists())

    def test_suggestions_are_owner_only_and_absent_for_hidden_or_disabled_ai(self):
        self.picture()
        for user in [self.member, self.outsider]:
            self.assertIsNone(workflow.suggestion(user, self.dictionary))
        self.client.force_login(self.member)
        self.assertNotContains(self.client.get(self.url('dictionary')), 'id="next-step"')
        for field, value in [('hidden', True), ('show_workflow_suggestions', False), ('sentence_capture_enabled', False), ('photo_ai_enabled', False), ('tts_enabled', False)]:
            old = getattr(self.dictionary, field)
            setattr(self.dictionary, field, value); self.dictionary.save()
            self.assertIsNone(self.step(), field)
            setattr(self.dictionary, field, old); self.dictionary.save()

    def test_one_click_starts_same_quote_and_duplicate_does_not_send_again(self):
        self.picture(); offer = self.step()
        with patch('community_dictionary.port_tasks.dispatch') as dispatch, self.captureOnCommitCallbacks(execute=True):
            self.assertEqual(self.start(offer['approval']).status_code, 302)
            self.assertEqual(self.start(offer['approval']).status_code, 302)
        self.assertEqual(dispatch.call_count, 1)
        run = PortRun.objects.get()
        self.assertEqual(run.status, 'running')
        self.assertEqual(run.estimated_usd, offer['estimated'])
        self.assertEqual(run.allowance_usd, offer['allowance'])
        self.assertEqual(run.items.count(), 1)
        self.assertEqual(self.step()['kind'], 'processing')

    def test_membership_requests_and_ready_reviews_take_priority(self):
        self.picture(); run = self.approve(self.quote()); self.process(run)
        self.picture()
        offer = self.step()
        self.assertEqual(offer['kind'], 'review')
        self.assertEqual(offer['label'], '1 sentence ready to review')
        MembershipRequest.objects.create(dictionary=self.dictionary, user=self.outsider)
        self.assertEqual(self.step()['kind'], 'requests')
        self.assertIn('?dictionary=', self.step()['url'])

    def test_after_sentence_review_offer_vocabulary_and_skip_current_words(self):
        self.picture(); run = self.approve(self.quote()); self.process(run)
        sentence = self.save(run.items.get())
        self.picture(); flagged = self.approve(self.quote()); self.process(flagged)
        flagged.items.update(needs_attention=True)
        offer = self.step(); self.assertEqual(offer['kind'], 'vocabulary')
        with patch('community_dictionary.port_tasks.dispatch'), self.captureOnCommitCallbacks(execute=True):
            self.assertEqual(self.start(offer['approval']).status_code, 302)
        words = PortRun.objects.get(stage='vocabulary')
        self.assertEqual(words.items.get().source_entry_id, sentence.pk)
        porting.cancel(self.owner, words.pk)
        VocabularyState.objects.create(sentence=sentence, snapshot=port_vocabulary.sentence_snapshot(sentence),
            recipe=port_vocabulary.VERSION, words=[], accepted_by=self.owner)
        self.assertIsNone(self.step())

    def test_changed_picture_hints_require_fresh_confirmation_and_roll_back_quote(self):
        entry = self.picture(meaning='cat'); token = self.step()['approval']
        add_contributions(entry, self.owner, {'meaning': 'dog', 'edit_text': True}, [], publish=True)
        response = self.start(token)
        self.assertEqual(response.status_code, 409)
        self.assertEqual(PortRun.objects.count(), 0)
        self.assertEqual(LanguagePort.objects.count(), 0)

    def test_more_pictures_after_estimate_cannot_silently_expand_approved_scope(self):
        self.picture(); token = self.step()['approval']; self.picture()
        self.assertEqual(self.start(token).status_code, 409)
        self.assertEqual(PortRun.objects.count(), 0)

    def test_model_price_or_payer_change_requires_fresh_confirmation(self):
        self.picture(); token = self.step()['approval']
        with patch('community_dictionary.photo_ai.configuration', return_value=('different-model', 'fixture-only', False, {'input': Decimal('2'), 'output': Decimal('8')})):
            self.assertEqual(self.start(token).status_code, 409)
        profile, _ = Profile.objects.get_or_create(user=self.owner)
        profile.use_personal_openai_key = True; profile.openai_api_key = 'personal-fixture'; profile.save()
        self.assertEqual(self.start(token).status_code, 409)
        self.assertEqual(PortRun.objects.count(), 0)

    def test_personal_key_disclosure_has_no_secret(self):
        self.picture()
        profile, _ = Profile.objects.get_or_create(user=self.owner)
        profile.use_personal_openai_key = True; profile.openai_api_key = 'SECRET-PERSONAL'; profile.save()
        response = self.client.get(self.url('dictionary'))
        self.assertContains(response, 'personal OpenAI account')
        self.assertNotContains(response, 'SECRET-PERSONAL')

    @override_settings(CREDITS_ENABLED=True)
    def test_credit_reservation_is_shown_checked_and_taken_once(self):
        self.picture()
        account, _ = CreditAccount.objects.get_or_create(user=self.owner)
        account.balance_usd = 100; account.save()
        offer = self.step()
        self.assertTrue(offer['enough_funds'])
        page = self.client.get(self.url('dictionary'))
        self.assertContains(page, 'Nothing has been reserved for this suggestion.')
        self.assertNotContains(page, 'Credit reserved:')
        self.assertFalse(CreditLedgerEntry.objects.filter(user=self.owner).exists())
        with patch('community_dictionary.port_tasks.dispatch'), self.captureOnCommitCallbacks(execute=True):
            self.assertEqual(self.start(offer['approval']).status_code, 302)
            self.assertEqual(self.start(offer['approval']).status_code, 302)
        account.refresh_from_db()
        self.assertEqual(account.balance_usd, Decimal('100') - offer['allowance'])
        self.assertEqual(CreditLedgerEntry.objects.filter(user=self.owner).count(), 1)

    @override_settings(CREDITS_ENABLED=True)
    def test_insufficient_funds_blocks_ui_and_post_without_job_or_reservation(self):
        self.picture(); offer = self.step()
        self.assertFalse(offer['enough_funds'])
        response = self.client.get(self.url('dictionary'))
        self.assertContains(response, 'Insufficient credit')
        self.assertNotContains(response, self.url('workflow-start'))
        self.assertEqual(self.start(offer['approval']).status_code, 409)
        self.assertEqual(PortRun.objects.count(), 0)
        self.assertEqual(CreditLedgerEntry.objects.filter(user=self.owner).count(), 0)

    def test_permission_token_csrf_post_only_and_expiry(self):
        self.picture(); token = self.step()['approval']
        self.assertEqual(self.client.get(self.url('workflow-start')).status_code, 405)
        self.assertEqual(self.start('not-signed').status_code, 409)
        csrf = Client(enforce_csrf_checks=True); csrf.force_login(self.owner)
        self.assertEqual(self.start(token, csrf).status_code, 403)
        member = Client(); member.force_login(self.member)
        self.assertEqual(self.start(token, member).status_code, 409)
        guest = Client(); self.assertEqual(self.start(token, guest).status_code, 302)
        with patch('django.core.signing.time.time', return_value=time.time() + workflow.MAX_AGE + 2):
            self.assertEqual(self.start(token).status_code, 409)
        self.assertEqual(PortRun.objects.count(), 0)

    def test_old_offer_cannot_start_after_owner_change_or_suggestions_disabled(self):
        self.picture(); token = self.step()['approval']
        Dictionary.objects.filter(pk=self.dictionary.pk).update(owner=self.member)
        self.assertEqual(self.start(token).status_code, 404)
        Dictionary.objects.filter(pk=self.dictionary.pk).update(owner=self.owner, show_workflow_suggestions=False)
        self.assertEqual(self.start(token).status_code, 409)
        self.assertEqual(PortRun.objects.count(), 0)

    def test_owner_toggle_stale_retry_and_nonowner_protection(self):
        path = self.url('workflow-setting')
        self.assertEqual(self.client.get(path).status_code, 405)
        for _ in range(2):
            self.assertEqual(self.client.post(path, {'action': 'disable', 'revision': 0}).status_code, 302)
        self.assertEqual(self.client.post(path, {'action': 'enable', 'revision': 0}).status_code, 409)
        self.dictionary.refresh_from_db(); self.assertFalse(self.dictionary.show_workflow_suggestions)
        self.assertEqual(self.dictionary.workflow_suggestions_revision, 1)
        self.assertEqual(self.client.post(path, {'action': 'enable', 'revision': 1}).status_code, 302)
        self.client.force_login(self.member)
        self.assertEqual(self.client.post(path, {'action': 'disable', 'revision': 2}).status_code, 404)
        csrf = Client(enforce_csrf_checks=True); csrf.force_login(self.owner)
        self.assertEqual(csrf.post(path, {'action': 'disable', 'revision': 2}).status_code, 403)

    def test_cancelled_approval_retry_cannot_restart_job(self):
        self.picture(); token = self.step()['approval']
        with patch('community_dictionary.port_tasks.dispatch'), self.captureOnCommitCallbacks(execute=True):
            self.start(token)
        run = PortRun.objects.get(); porting.cancel(self.owner, run.pk)
        with patch('community_dictionary.port_tasks.dispatch') as dispatch:
            self.assertEqual(self.start(token).status_code, 302)
        run.refresh_from_db(); self.assertEqual(run.status, 'cancelled')
        dispatch.assert_not_called()

    def test_private_guidance_never_appears_in_public_directory_or_pages(self):
        self.picture()
        Dictionary.objects.filter(pk=self.dictionary.pk).update(public_browsing_enabled=True, discoverable=True)
        self.client.logout()
        for path in [self.url('public-dictionary'), reverse('community_dictionary:public-home')]:
            self.assertNotContains(self.client.get(path), 'ready for sentences')

    def test_missing_api_key_is_a_local_message_not_a_browse_failure(self):
        self.picture()
        with override_settings(OPENAI_API_KEY=''):
            response = self.client.get(self.url('dictionary'))
            self.assertContains(response, 'ask the administrator')
            self.assertNotContains(response, self.url('workflow-start'))
        self.assertEqual(PortRun.objects.count(), 0)
