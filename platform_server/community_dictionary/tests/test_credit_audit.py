"""Financial audit must distinguish a quote, a hold and a settled charge."""
from datetime import timedelta
from decimal import Decimal
from io import StringIO
from unittest.mock import patch
import uuid

from django.contrib.auth import get_user_model
from django.core.management import call_command, CommandError
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from community_dictionary.models import Dictionary, Entry, LanguagePort, PortRun, PortItem
from projects.billing import apply_credit_delta
from projects.models import CreditAccount, CreditLedgerEntry


class CreditAuditTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='audit-owner')
        self.other = get_user_model().objects.create_user(username='unrelated')
        self.dictionary = Dictionary.objects.create(owner=self.user, name='PRIVATE DICTIONARY', language='Swedish')
        self.port = LanguagePort.objects.create(source=self.dictionary, user=self.user,
            name='PRIVATE PORT NAME', language='French', explanation_language='English')
        CreditAccount.objects.update_or_create(user=self.user, defaults={'balance_usd': Decimal('100')})

    def run_record(self, **kwargs):
        return PortRun.objects.create(port=self.port, stage='vocabulary', model='fixture', payer='credits',
            expires_at=timezone.now()+timedelta(hours=1), **kwargs)

    def entry(self, run, amount, kind):
        return apply_credit_delta(user=self.user, amount_usd=Decimal(amount),
            entry_type=CreditLedgerEntry.ENTRY_USAGE, description='fixture',
            metadata={'port_run': str(run.pk), 'kind':kind})

    def audit(self):
        output = StringIO()
        # The CLI has no provider/queue paths; also guard against accidental wiring.
        with patch('community_dictionary.port_tasks.dispatch', side_effect=AssertionError('no jobs')), \
             patch('community_dictionary.photo_ai._openai_client', side_effect=AssertionError('no API')), \
             CaptureQueriesContext(connection) as queries:
            call_command('community_credit_audit', username=self.user.username, stdout=output)
        for query in queries:
            self.assertFalse(query['sql'].lstrip().upper().startswith(('INSERT ', 'UPDATE ', 'DELETE ')), query['sql'])
        self.assertNotIn('PRIVATE', output.getvalue())
        return output.getvalue()

    def test_quote_hold_settlement_and_reuse_are_distinguished_without_mutation(self):
        self.run_record(allowance_usd=90, estimated_usd=5)
        held = self.run_record(status='running', reserved_usd=20, allowance_usd=20)
        self.entry(held, '-20', 'reservation')
        source = Entry.objects.create(dictionary=self.dictionary, created_by=self.user)
        PortItem.objects.create(run=held, source_entry=source, status='ready', translation_cost=Decimal('.012'))
        settled = self.run_record(status='complete', settled=True, reserved_usd=30, charged_usd=Decimal('.5'))
        self.entry(settled, '-30', 'reservation'); self.entry(settled, '29.5', 'refund')
        # Unrelated account's ledger must not appear or affect totals.
        apply_credit_delta(user=self.other, amount_usd=Decimal('-9'), entry_type='usage',
            description='private', metadata={'port_run':str(uuid.uuid4()), 'kind':'reservation'})
        text = self.audit()
        self.assertIn('NOT held, may be expired): US$90.0000', text)
        self.assertIn('Outstanding holds according to job records: US$20.0000', text)
        self.assertIn('Final charges for settled credit jobs: US$0.5000', text)
        self.assertIn('Net batch ledger deduction (holds plus final charges): US$20.5000', text)
        self.assertIn("items={'ready': 1}", text)
        self.assertIn('Reconciliation warnings: 0', text)
        self.assertEqual(text, self.audit())
        self.assertEqual(CreditAccount.objects.get(user=self.user).balance_usd, Decimal('79.5'))

    def test_missing_refund_is_flagged_without_refunding(self):
        run = self.run_record(status='complete', settled=True, reserved_usd=10, charged_usd=1)
        self.entry(run, '-10', 'reservation')
        text = self.audit()
        self.assertIn('refund ledger differs from job record', text)
        self.assertIn('net batch ledger deduction differs', text)
        self.assertEqual(CreditAccount.objects.get(user=self.user).balance_usd, Decimal(90))

    def test_duplicate_refund_and_orphan_are_flagged(self):
        run = self.run_record(status='complete', settled=True, reserved_usd=10, charged_usd=1)
        self.entry(run, '-10', 'reservation')
        self.entry(run, '9', 'refund'); self.entry(run, '9', 'refund')
        apply_credit_delta(user=self.user, amount_usd=Decimal('-1'), entry_type='usage',
            metadata={'port_run':str(uuid.uuid4()), 'kind':'reservation'}, description='fixture')
        text = self.audit()
        self.assertIn('refund ledger differs from job record', text)
        self.assertIn('ledger references missing or differently owned run', text)

    def test_unknown_user_or_absent_credit_account_never_creates_one(self):
        with self.assertRaises(CommandError):
            call_command('community_credit_audit', username='missing', stdout=StringIO())
        CreditAccount.objects.filter(user=self.user).delete()
        text = self.audit()
        self.assertIn('no credit account', text)
        self.assertFalse(CreditAccount.objects.filter(user=self.user).exists())
