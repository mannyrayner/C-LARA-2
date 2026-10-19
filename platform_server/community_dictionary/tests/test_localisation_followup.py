"""Screenshot regressions: localise controls, preserve content and permissions."""
from decimal import Decimal
from unittest.mock import patch

from django.template.defaultfilters import floatformat
from django.test import TestCase, override_settings
from django.utils import timezone, translation
from django.utils.html import escape
from django.utils.translation import gettext, ngettext

from community_dictionary.localisation import UI_COOKIE, language_label
from community_dictionary.models import (
    AttentionReport, Contribution, Event, LanguagePort, Membership,
    MembershipRequest, Partner, Partnership, Participation, PortRun,
)
from projects.models import CreditAccount, CreditLedgerEntry, Profile
from . import test_batch_descriptions as fixtures


@override_settings(OPENAI_API_KEY='fixture-only', CREDITS_ENABLED=False)
class LocalisationFollowupTests(TestCase):
    setUp = fixtures.BatchDescriptionTests.setUp
    url = fixtures.BatchDescriptionTests.url
    post = fixtures.BatchDescriptionTests.post
    picture = fixtures.BatchDescriptionTests.picture
    create_entry = fixtures.BatchDescriptionTests.create_entry
    quote = fixtures.BatchDescriptionTests.quote
    approve = fixtures.BatchDescriptionTests.approve
    process = fixtures.BatchDescriptionTests.process
    save = fixtures.BatchDescriptionTests.save

    def french(self):
        self.client.cookies[UI_COOKIE] = 'fr'

    def assert_translated(self, response, *messages):
        with translation.override('fr'):
            for message in messages:
                translated = gettext(message)
                self.assertNotEqual(translated, message, message)
                self.assertContains(response, escape(translated), msg_prefix=message)

    def plural(self, singular, plural, count):
        with translation.override('fr'):
            return ngettext(singular, plural, count) % {'count': count}

    def assert_translated_html(self, response, message, **values):
        with translation.override('fr'):
            translated = gettext(message)
            self.assertNotEqual(translated, message)
            self.assertContains(response, '<p>%s</p>' % (translated % values), html=True)

    def test_dictionary_language_heading_localises_without_rewriting_content(self):
        self.dictionary.language = 'English'
        self.dictionary.explanation_language = 'French'
        self.dictionary.name = 'English words, our own title'
        self.dictionary.save()
        entry = self.picture(word='English', meaning='Our original English explanation')
        self.french()
        page = self.client.get(self.url('dictionary'))
        with translation.override('fr'):
            self.assertContains(page, '<p class="eyebrow">%s</p>' % language_label('English'), html=True)
        self.assertContains(page, self.dictionary.name)
        self.assertContains(page, 'Our original English explanation')
        self.dictionary.refresh_from_db(); entry.refresh_from_db()
        self.assertEqual(self.dictionary.language, 'English')
        self.assertEqual(self.dictionary.explanation_language, 'French')
        self.assertEqual(entry.word, 'English')
        self.assertEqual(entry.meaning, 'Our original English explanation')
        self.client.cookies[UI_COOKIE] = 'en'
        self.assertContains(self.client.get(self.url('dictionary')), '<p class="eyebrow">English</p>', html=True)

    def test_attention_empty_states_are_french_and_switch_back_to_english(self):
        self.french()
        page = self.client.get(self.url('attention'))
        self.assert_translated(page, 'Needs attention', 'No open reports.',
            'Any member can flag an entry. Dictionary owners and editors can correct it and mark the current wording checked.',
            'AI-assisted wording not yet checked by an editor',
            'Already shared and available to learn from. This is a review aid, not an approval barrier. Up to 100 recent entries.',
            'No entries waiting for a language check.')
        self.client.cookies[UI_COOKIE] = 'en'
        page = self.client.get(self.url('attention'))
        for message in ['Needs attention', 'No open reports.', 'No entries waiting for a language check.']:
            self.assertContains(page, message)

    def test_attention_reports_and_unchecked_entries_keep_contributor_text(self):
        entry = self.picture(word='A cat is sleeping.', meaning='Le chat dort.')
        entry.refresh_from_db()
        text = entry.current_text
        text.provenance = {'origin': 'picture-description'}; text.save()
        note = Contribution.objects.create(entry=entry, author=self.member, kind='note',
            status='accepted', body='Please keep my English note unchanged.')
        report = AttentionReport.objects.create(entry=entry, note=note)
        self.french()
        page = self.client.get(self.url('attention'))
        self.assert_translated(page, 'Needs attention', 'AI-assisted wording not yet checked by an editor')
        self.assertContains(page, 'A cat is sleeping.')
        self.assertContains(page, note.body)
        with translation.override('fr'):
            self.assertNotContains(page, gettext('No open reports.'))
        self.assertEqual(list(page.context['reports']), [report])
        self.assertEqual(list(page.context['unchecked']), [entry])
        report.resolved_at = timezone.now(); report.resolved_by = self.owner; report.save()
        page = self.client.get(self.url('attention'))
        self.assertNotContains(page, note.body)
        self.assert_translated(page, 'No open reports.')
        note.refresh_from_db(); self.assertEqual(note.body, 'Please keep my English note unchanged.')

    def test_people_owner_controls_roles_statuses_and_partnerships_are_french(self):
        Membership.objects.filter(dictionary=self.dictionary, user=self.member).update(role='editor')
        Membership.objects.filter(dictionary=self.dictionary, user=self.third).update(role='coordinator', status='inactive')
        Membership.objects.create(dictionary=self.dictionary, user=self.outsider)
        Participation.objects.create(dictionary=self.dictionary, user=self.third, withdrawn=True)
        Partner.objects.filter(partnership=self.group, user=self.third).update(accepted=False)
        invitation = Partnership.objects.create(dictionary=self.dictionary,
            name='Our English partnership title', created_by=self.member)
        Partner.objects.create(partnership=invitation, user=self.member, accepted=True)
        Partner.objects.create(partnership=invitation, user=self.owner)
        self.french()
        page = self.client.get(self.url('people'))
        self.assert_translated(page, 'People & partnerships',
            'Build together. Everyone keeps their own account and contribution credit.',
            'Dictionary members', 'Owner', 'Editor', 'Coordinator', 'Member',
            'Active', 'Inactive', 'Invited', 'Joined', 'Content withdrawn',
            'Role', 'Request role change', 'Make inactive', 'Reactivate membership',
            'Invite an account', 'Existing C-LARA account', 'Save invitation or role',
            'New invitations appear on the person’s Community dictionaries page. No email is sent.',
            'Your partnerships', 'Add another partner', 'Invite partner', 'Leave partnership',
            'Join partnership', 'Create a partnership', 'Partnership name', 'Create partnership',
            'People must join the dictionary before they can be invited to a partnership.')
        for name in [self.dictionary.name, self.group.name, invitation.name, self.member.username]:
            self.assertContains(page, name)
        for field in ['name="action" value="invite"', 'name="action" value="join_group"',
                      'name="action" value="leave_group"', 'name="action" value="create_group"']:
            self.assertContains(page, field)

    def test_member_and_editor_people_pages_keep_existing_permission_boundaries(self):
        self.french()
        for role in ['member', 'editor']:
            with self.subTest(role=role):
                Membership.objects.filter(dictionary=self.dictionary, user=self.member).update(role=role)
                self.client.force_login(self.member)
                page = self.client.get(self.url('people'))
                self.assert_translated(page, 'People & partnerships', 'Create partnership')
                self.assertContains(page, 'name="action" value="create_group"')
                self.assertNotContains(page, 'name="action" value="invite"')
                self.assertNotContains(page, 'name="action" value="role"')
                self.assertNotContains(page, 'name="action" value="deactivate"')
                denied = self.client.post(self.url('people'), {
                    'action': 'invite', 'username': self.outsider.username, 'role': 'editor'})
                self.assertEqual(denied.status_code, 404)
        self.assertFalse(Membership.objects.filter(dictionary=self.dictionary, user=self.outsider).exists())
        self.client.force_login(self.outsider)
        for route in ['people', 'attention']:
            self.assertEqual(self.client.get(self.url(route)).status_code, 404)

    def test_people_partnership_empty_state_is_translated(self):
        Partner.objects.filter(user=self.owner).delete()
        self.french()
        page = self.client.get(self.url('people'))
        self.assert_translated(page, 'You haven’t joined a partnership yet.', 'Create a partnership')
        self.client.cookies[UI_COOKIE] = 'en'
        page = self.client.get(self.url('people'))
        self.assertContains(page, '<h1>People &amp; partnerships</h1>', html=True)
        self.assertContains(page, 'You haven’t joined a partnership yet.')

    def test_description_card_localises_counts_details_and_is_read_only(self):
        self.picture(word='katt')
        self.french()
        for count in [1, 2]:
            with self.subTest(count=count):
                if count == 2:
                    self.picture(pending=True)
                before = (LanguagePort.objects.count(), PortRun.objects.count(), Event.objects.count())
                with patch('community_dictionary.batch_descriptions.interpret') as api, \
                     patch('community_dictionary.tts.synthesize') as speech, \
                     patch('community_dictionary.port_tasks.dispatch') as dispatch:
                    page = self.client.get(self.url('dictionary'))
                api.assert_not_called(); speech.assert_not_called(); dispatch.assert_not_called()
                self.assertEqual(page.context['next_step']['kind'], 'descriptions')
                expected = self.plural('%(count)s picture ready for sentences',
                    '%(count)s pictures ready for sentences', count)
                self.assertContains(page, expected)
                self.assert_translated(page, 'Next step', 'Approve and create sentences',
                    'Accepted pictures and pictures awaiting review, keeping existing words and translations as hints.',
                    'What will be sent and created?', 'Paid by the server operator. The estimate is not a provider spending cap.')
                self.assertContains(page, 'name="approval"')
                self.assertContains(page, self.url('workflow-start'))
                self.assertFalse(CreditLedgerEntry.objects.filter(user=self.owner).exists())
                self.assertEqual((LanguagePort.objects.count(), PortRun.objects.count(), Event.objects.count()), before)
        self.client.cookies[UI_COOKIE] = 'en'
        self.assertContains(self.client.get(self.url('dictionary')), '2 pictures ready for sentences')

    def test_next_step_is_owner_only_in_french(self):
        self.picture(); self.french()
        for user in [self.member, self.outsider]:
            self.client.force_login(user)
            page = self.client.get(self.url('dictionary'))
            if user == self.outsider:
                self.assertEqual(page.status_code, 404)
            else:
                self.assertNotContains(page, 'id="next-step"')

    def test_membership_request_singular_and_plural_render_in_french(self):
        self.french()
        for count, user in [(1, self.outsider), (2, self.third)]:
            MembershipRequest.objects.create(dictionary=self.dictionary, user=user)
            page = self.client.get(self.url('dictionary'))
            self.assertEqual(page.context['next_step']['kind'], 'requests')
            self.assertContains(page, self.plural('%(count)s membership request',
                '%(count)s membership requests', count))
            self.assert_translated(page, 'View requests', 'Next step')

    def test_processing_budget_and_review_then_vocabulary_cards_are_french(self):
        self.picture(); self.french()
        run = self.approve(self.quote())
        page = self.client.get(self.url('dictionary'))
        self.assert_translated(page, 'Processing…', 'View progress')
        run.items.update(status='budget')
        page = self.client.get(self.url('dictionary'))
        self.assert_translated(page, 'More allowance needs your approval', 'Review allowance')
        run.items.update(status='queued')
        self.process(run)
        page = self.client.get(self.url('dictionary'))
        self.assertEqual(page.context['next_step']['kind'], 'review')
        self.assertContains(page, self.plural('%(count)s sentence ready to review',
            '%(count)s sentences ready to review', 1))
        self.assert_translated(page, 'Review sentences')
        self.save(run.items.get())
        page = self.client.get(self.url('dictionary'))
        self.assertEqual(page.context['next_step']['kind'], 'vocabulary')
        self.assert_translated(page, 'Word pages ready to create', 'Approve and create word suggestions')
        self.assertContains(page, self.plural('Words and expressions from %(count)s accepted sentence',
            'Words and expressions from %(count)s accepted sentences', 1))

    @override_settings(CREDITS_ENABLED=True)
    def test_credit_information_and_personal_key_disclosure_are_french_without_spending(self):
        self.picture(); self.french()
        account, _ = CreditAccount.objects.get_or_create(user=self.owner)
        account.balance_usd = Decimal('100'); account.save()
        page = self.client.get(self.url('dictionary'))
        self.assertTrue(page.context['next_step']['enough_funds'])
        with translation.override('fr'):
            self.assert_translated_html(page,
                'Credit needed to start: <strong>US$%(allowance)s</strong> (refundable allowance). Available: <strong>US$%(balance)s</strong>. Nothing has been reserved for this suggestion. Approval reserves the allowance; unused credit is returned as each item finishes its processing and any vocabulary review/audio. Further allowance needs your approval; cancellation waits for any in-flight requests.',
                allowance=floatformat(page.context['next_step']['allowance'], 4),
                balance=floatformat(page.context['next_step']['balance'], 4))
        self.assertFalse(CreditLedgerEntry.objects.filter(user=self.owner).exists())
        account.refresh_from_db(); self.assertEqual(account.balance_usd, Decimal('100'))
        account.balance_usd = 0; account.save()
        page = self.client.get(self.url('dictionary'))
        self.assertFalse(page.context['next_step']['enough_funds'])
        self.assert_translated(page, 'Insufficient credit for the reservation.')
        self.assertNotContains(page, self.url('workflow-start'))
        profile, _ = Profile.objects.get_or_create(user=self.owner)
        profile.use_personal_openai_key = True; profile.openai_api_key = 'PERSONAL-KEY-NEVER-DISPLAY'; profile.save()
        page = self.client.get(self.url('dictionary'))
        self.assert_translated(page, 'Paid through your personal OpenAI account; its balance cannot be checked here. The estimate is not a provider spending cap.')
        self.assertNotContains(page, profile.openai_api_key)
        self.assertEqual(PortRun.objects.count(), 0)
        self.assertFalse(CreditLedgerEntry.objects.filter(user=self.owner).exists())

    def test_french_catalogue_uses_french_zero_one_and_two_plural_rules(self):
        # The UI suppresses zero-work offers. Check zero directly as well so a
        # future offer cannot accidentally inherit the English plural rule.
        for singular, plural in [
            ('%(count)s picture ready for sentences', '%(count)s pictures ready for sentences'),
            ('%(count)s membership request', '%(count)s membership requests'),
            ('%(count)s sentence ready to review', '%(count)s sentences ready to review'),
            ('%(count)s entry ready to review', '%(count)s entries ready to review'),
            ('Word suggestions for %(count)s sentence ready to review', 'Word suggestions for %(count)s sentences ready to review'),
            ('Words and expressions from %(count)s accepted sentence', 'Words and expressions from %(count)s accepted sentences'),
        ]:
            with self.subTest(singular=singular), translation.override('fr'):
                forms = [ngettext(singular, plural, count) for count in [0, 1, 2]]
                self.assertNotEqual(forms[0], singular)
                self.assertEqual(forms[0], forms[1])
                self.assertNotEqual(forms[1], forms[2])
