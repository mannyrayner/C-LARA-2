"""Read-only reconciliation of batch reservations with their credit ledger rows."""
from collections import Counter, defaultdict
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction

from community_dictionary.models import PortItem, PortRun, PortSpeech
from projects.models import CreditAccount, CreditLedgerEntry

ZERO = Decimal('0')


class Command(BaseCommand):
    help = 'Read-only audit of Community Dictionary batch credit holds; no AI calls or refunds.'

    def add_arguments(self, parser):
        parser.add_argument('--username', required=True, help='Exact login name, not email.')

    def handle(self, *args, **options):
        # A consistent snapshot avoids false discrepancies while workers settle.
        # SET TRANSACTION must precede the first data query on PostgreSQL.
        with transaction.atomic():
            if connection.vendor == 'postgresql':
                with connection.cursor() as cursor:
                    cursor.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY')
            self.audit(options['username'])

    def audit(self, username):
        user_id = get_user_model().objects.filter(username=username).values_list('pk', flat=True).first()
        if user_id is None:
            raise CommandError('No account has that login name. No changes made.')
        balance = CreditAccount.objects.filter(user_id=user_id).values_list('balance_usd', flat=True).first()
        runs = list(PortRun.objects.filter(port__user_id=user_id).order_by('created_at'))
        known = {str(run.pk): run for run in runs}
        ledger = defaultdict(list)
        for row in CreditLedgerEntry.objects.filter(user_id=user_id).values('amount_usd', 'metadata'):
            if row['metadata'].get('port_run') is not None:
                ledger[str(row['metadata']['port_run'])].append(row)
        items, clips = defaultdict(Counter), defaultdict(Counter)
        known_cost, uncertain = defaultdict(lambda: ZERO), Counter()
        for row in PortItem.objects.filter(run__port__user_id=user_id).values(
                'run_id', 'status', 'translation_cost', 'audio_cost', 'uncertain_cost'):
            key = str(row['run_id'])
            items[key][row['status']] += 1
            known_cost[key] += row['translation_cost'] + row['audio_cost']
            uncertain[key] += int(row['uncertain_cost'])
        for row in PortSpeech.objects.filter(run__port__user_id=user_id).values('run_id', 'status'):
            clips[str(row['run_id'])][row['status']] += 1

        self.stdout.write('READ ONLY: no API requests, refunds, cancellations or account changes.')
        self.stdout.write(f'Account ID: {user_id}; available C-LARA credit: {balance if balance is not None else "no credit account"}')
        proposed = sum((r.allowance_usd for r in runs if r.payer == 'credits' and r.status == 'estimate'), ZERO)
        held = sum((r.reserved_usd for r in runs if r.payer == 'credits' and not r.settled), ZERO)
        charged = sum((r.charged_usd for r in runs if r.payer == 'credits' and r.settled), ZERO)
        self.stdout.write(f'Unapproved quote allowances (NOT held, may be expired): US${proposed:.4f}')
        self.stdout.write(f'Outstanding holds according to job records: US${held:.4f}')
        self.stdout.write(f'Final charges for settled credit jobs: US${charged:.4f}')
        warnings = []
        for run in runs:
            key = str(run.pk)
            rows = ledger.get(key, [])
            reservations = [r['amount_usd'] for r in rows if r['metadata'].get('kind') == 'reservation']
            refunds = [r['amount_usd'] for r in rows if r['metadata'].get('kind') == 'refund']
            expected_debit = -run.reserved_usd if run.payer == 'credits' else ZERO
            expected_refund = run.reserved_usd - run.charged_usd if run.payer == 'credits' and run.settled else ZERO
            issues = []
            if sum(reservations, ZERO) != expected_debit or len(reservations) != int(expected_debit != 0):
                issues.append('reservation ledger differs from job record')
            if sum(refunds, ZERO) != expected_refund or len(refunds) != int(expected_refund != 0):
                issues.append('refund ledger differs from job record')
            if len(rows) != len(reservations) + len(refunds):
                issues.append('unrecognised batch ledger rows')
            if run.payer == 'credits' and (run.charged_usd < 0 or run.charged_usd > run.reserved_usd):
                issues.append('final charge outside reservation')
            if not run.settled and run.reserved_usd and run.status != 'running':
                issues.append('unsettled hold outside running job: inspect remaining work')
            if run.reserved_usd or rows or issues:
                self.stdout.write(f'\nRun {key}; {run.stage}; {run.status}; settled={run.settled}; created={run.created_at.isoformat()}')
                self.stdout.write(f'  estimate={run.estimated_usd}; original reservation={run.reserved_usd}; '
                    f'ledger refund={sum(refunds, ZERO):.4f}; final charge={run.charged_usd}; '
                    f'held={ZERO if run.settled else run.reserved_usd:.4f}')
                self.stdout.write(f'  recorded usage estimate={known_cost[key]:.6f}; uncertain items={uncertain[key]}')
                self.stdout.write(f'  items={dict(sorted(items[key].items()))}; audio={dict(sorted(clips[key].items()))}')
                for issue in issues:
                    self.stdout.write(f'  CHECK: {issue}')
                    warnings.append(issue)
        for key in ledger.keys() - known.keys():
            self.stdout.write(f'CHECK: ledger references missing or differently owned run {key}')
            warnings.append('orphan ledger reference')
        net = -sum((r['amount_usd'] for rows in ledger.values() for r in rows), ZERO)
        self.stdout.write(f'\nNet batch ledger deduction (holds plus final charges): US${net:.4f}')
        if net != held + charged:
            warnings.append('aggregate difference')
            self.stdout.write('CHECK: net batch ledger deduction differs from holds plus final charges.')
        latest = CreditLedgerEntry.objects.filter(user_id=user_id).order_by('-id').values_list('balance_after_usd', flat=True).first()
        if latest is not None and latest != balance:
            warnings.append('latest account ledger balance differs')
            self.stdout.write('CHECK: available credit differs from the latest account ledger balance.')
        self.stdout.write(f'Reconciliation warnings: {len(warnings)}')
        self.stdout.write('Ready/unclear vocabulary suggestions can keep a hold until review/audio finish. '
            'Recorded usage is not a provider invoice. No automatic correction has been made.')
