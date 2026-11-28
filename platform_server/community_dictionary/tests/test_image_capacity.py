"""Shared payer admission and fair dispatch; provider calls are always mocked."""
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from decimal import Decimal
import io
import json
from pathlib import Path
from threading import Event, Lock
import tempfile
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import close_old_connections, connection, transaction
from django.test import TestCase, TransactionTestCase, override_settings
from django.utils import timezone
from PIL import Image

from community_dictionary import capture, image_capacity as capacity, image_generation as images
from community_dictionary import lemma_images as pictures, lemma_picture_costs as costs
from community_dictionary.models import Dictionary, Entry, ImageStudy, LemmaImage
from community_dictionary.services import Conflict
from projects.models import AIUsageCharge


class Fixtures:
    def setUp(self):
        super().setUp()
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        configured = override_settings(COMMUNITY_DICTIONARY_MEDIA_ROOT=Path(temporary.name))
        configured.enable(); self.addCleanup(configured.disable)
        self.owner = get_user_model().objects.create_user('payer')
        self.other = get_user_model().objects.create_user('other')
        self.a = Dictionary.objects.create(owner=self.owner, name='A', language='Swedish',
            explanation_language='English', image_generation_enabled=True, automatic_word_images=False)
        self.b = Dictionary.objects.create(owner=self.owner, name='B', language='Swedish',
            explanation_language='English', image_generation_enabled=True, automatic_word_images=False)
        self.queue = patch.object(pictures, 'queue').start()
        # Keep provider/background work inside the explicitly mocked test call.
        self.addCleanup(patch.stopall)

    def receipt(self, dictionary=None, user=None, **extra):
        return ImageStudy.objects.create(dictionary=dictionary or self.a, user=user or self.owner,
            kind='entry', expires_at=timezone.now()+timedelta(days=1), **extra)

    def admit(self, dictionary=None, user=None, amount='0.50', **kwargs):
        with transaction.atomic():
            slot = capacity.reserve(user or self.owner, amount, **kwargs)
            return self.receipt(dictionary, user, usage={capacity.KEY: slot}, personal_key=kwargs.get('personal', False))

    def word(self, dictionary, batch):
        entry = Entry.objects.create(dictionary=dictionary, created_by=self.owner)
        capture.component(entry, self.owner, 'word', 'katt', {})
        capture.component(entry, self.owner, 'meaning', 'cat', {})
        with transaction.atomic():
            row = pictures.request(entry, self.owner)
            row.study = costs.create_study(row, batch=batch)
            row.save(update_fields=['study'])
        return row


@override_settings(OPENAI_API_KEY='fixture-not-real', CREDITS_ENABLED=False,
    COMMUNITY_DICTIONARY_IMAGE_CONCURRENCY=2, COMMUNITY_DICTIONARY_IMAGE_DAILY_LIMIT=20,
    COMMUNITY_DICTIONARY_IMAGE_ALLOWANCE_USD='0.50')
class AdmissionTests(Fixtures, TestCase):
    def test_two_slots_shared_across_dictionaries_but_not_payers(self):
        self.admit(self.a); self.admit(self.b)
        with self.assertRaises(capacity.Busy): self.admit()
        self.admit(user=self.other)
        self.assertEqual(capacity.active(self.owner.pk).count(), 2)

    def test_configured_single_slot_and_invalid_configuration(self):
        with override_settings(COMMUNITY_DICTIONARY_IMAGE_CONCURRENCY=1):
            self.admit()
            with self.assertRaises(capacity.Busy): self.admit()
        from community_dictionary.checks import picture_concurrency
        for value in [0, 5, 'invalid']:
            with override_settings(COMMUNITY_DICTIONARY_IMAGE_CONCURRENCY=value):
                self.assertEqual(picture_concurrency(None)[0].id, 'community_dictionary.E002')

    def test_credit_reserved_until_receipt_finishes_and_personal_key_not_charged(self):
        with override_settings(CREDITS_ENABLED=True), patch.object(capacity, 'get_user_balance_usd', return_value=Decimal('0.75')):
            first = self.admit()
            with self.assertRaises(capacity.Busy): self.admit(self.b)
            first.status='saved'; first.save(update_fields=['status'])
            self.admit(self.b)
            personal = self.admit(personal=True)
            self.assertEqual(personal.usage[capacity.KEY]['reserved_usd'], '0')

    def test_unstarted_bulk_receipts_and_completed_attempts_do_not_hold_slots(self):
        for _ in range(4): self.word(self.a, 'large')
        self.admit(); self.admit()
        self.assertEqual(capacity.active(self.owner.pk).count(), 2)

    def test_legacy_receipt_reserves_configured_estimate(self):
        self.receipt()
        with override_settings(CREDITS_ENABLED=True), patch.object(capacity, 'get_user_balance_usd', return_value=Decimal('0.75')):
            with self.assertRaises(Conflict): self.admit()

    def test_reservation_survives_accounting_and_release_wakes_queue(self):
        self.word(self.a, 'waiting')
        receipt=self.admit()
        with transaction.atomic():
            images.account(receipt, {'prompt_tokens':100,'completion_tokens':200})
            receipt.status='saved'; receipt.save()
        receipt.refresh_from_db()
        self.assertEqual(receipt.usage[capacity.KEY]['reserved_usd'], '0.50')
        with self.captureOnCommitCallbacks(execute=True): capacity.wake(self.owner.pk)
        self.queue.assert_called_once()

    def test_stale_receipt_is_not_retried_by_dispatcher(self):
        receipt=self.receipt()
        ImageStudy.objects.filter(pk=receipt.pk).update(created_at=timezone.now()-timedelta(seconds=images.TIMEOUT+121))
        self.assertFalse(capacity.active(self.owner.pk).exists())
        self.assertIsNone(capacity.next_word(self.owner.pk))
        receipt.refresh_from_db(); self.assertEqual(receipt.status, 'processing')


@override_settings(OPENAI_API_KEY='fixture-not-real', CREDITS_ENABLED=False,
    COMMUNITY_DICTIONARY_IMAGE_CONCURRENCY=2, COMMUNITY_DICTIONARY_IMAGE_DAILY_LIMIT=20,
    COMMUNITY_DICTIONARY_IMAGE_ALLOWANCE_USD='0.50')
class FairDispatchTests(Fixtures, TestCase):
    def test_new_small_batch_gets_slot_alongside_active_large_batch(self):
        large=[self.word(self.a,'large') for _ in range(4)]
        small=self.word(self.b,'small')
        costs.track(large[0].study, started=True)
        large[0].status='generating'; large[0].save(update_fields=['status'])
        self.assertEqual(capacity.next_word(self.owner.pk).pk, small.pk)

    def test_distinct_batches_within_one_dictionary_are_fair_and_fifo(self):
        first=self.word(self.a,'one'); second=self.word(self.a,'one'); third=self.word(self.a,'two')
        self.assertEqual(capacity.next_word(self.owner.pk).pk, first.pk)
        costs.track(first.study, started=True)
        first.status='ready'; first.save(update_fields=['status'])
        first.study.status='saved'; first.study.save(update_fields=['status'])
        self.assertEqual(capacity.next_word(self.owner.pk).pk, third.pk)
        costs.track(third.study, started=True)
        third.status='ready'; third.save(update_fields=['status'])
        third.study.status='saved'; third.study.save(update_fields=['status'])
        self.assertEqual(capacity.next_word(self.owner.pk).pk, second.pk)

    def test_busy_word_stays_waiting_without_paid_stage(self):
        row=self.word(self.a,'batch')
        self.admit(); self.admit()
        with patch.object(pictures,'analyse') as paid:
            self.assertFalse(pictures.run(row.pk,row.revision))
        row.refresh_from_db(); self.assertEqual(row.status,'waiting')
        paid.assert_not_called()
        self.assertFalse(row.study.usage[costs.KEY]['started'])

    def test_reserved_credit_defers_word_until_running_picture_finishes(self):
        row=self.word(self.a,'batch')
        first=self.admit()
        with override_settings(CREDITS_ENABLED=True), patch.object(capacity,'get_user_balance_usd',return_value=Decimal('0.75')):
            with patch.object(pictures,'analyse') as paid:
                self.assertFalse(pictures.run(row.pk,row.revision))
            paid.assert_not_called()
        row.refresh_from_db(); self.assertEqual(row.status,'waiting')
        first.status='saved'; first.save(update_fields=['status'])
        self.assertEqual(capacity.next_word(self.owner.pk).pk,row.pk)


@override_settings(OPENAI_API_KEY='fixture-not-real', CREDITS_ENABLED=False,
    COMMUNITY_DICTIONARY_IMAGE_CONCURRENCY=2, COMMUNITY_DICTIONARY_IMAGE_DAILY_LIMIT=20,
    COMMUNITY_DICTIONARY_IMAGE_ALLOWANCE_USD='0.50')
class PostgreSQLRaceTests(Fixtures, TransactionTestCase):
    def setUp(self):
        if connection.vendor != 'postgresql': self.skipTest('Row-lock races require PostgreSQL; dedicated CI job runs them.')
        super().setUp()

    def threaded(self, fn):
        close_old_connections()
        try: return fn()
        finally: close_old_connections()

    def test_parallel_admission_is_serialized_by_payer_credit_lock(self):
        with override_settings(CREDITS_ENABLED=True), patch.object(capacity,'get_user_balance_usd',return_value=Decimal('0.75')):
            def try_admit():
                try: self.admit(); return True
                except Conflict: return False
            with ThreadPoolExecutor(max_workers=3) as pool:
                results=list(pool.map(lambda _: self.threaded(try_admit),range(3)))
        self.assertEqual(results.count(True),1)
        self.assertEqual(ImageStudy.objects.count(),1)

    def test_three_dispatchers_make_two_distinct_paid_calls_and_redelivery_is_free(self):
        rows=[self.word(self.a,'large'),self.word(self.a,'large'),self.word(self.b,'small')]
        both=Event(); release=Event(); lock=Lock(); entered=[]
        data=io.BytesIO(); Image.new('RGB',(20,20),'green').save(data,'PNG')
        response=SimpleNamespace(status='completed',usage=SimpleNamespace(input_tokens=100,output_tokens=50),
            output_text=json.dumps({'suitability':'clue','subject':'A cat on a plain background.'}))
        def generate(study,key):
            with lock:
                entered.append(study.pk)
                if len(entered)==2: both.set()
            if not release.wait(15): raise AssertionError('The second worker did not enter concurrently.')
            return (data.getvalue(),'image/png','.png'), {'prompt_tokens':100,'completion_tokens':200}, ''
        with patch.object(pictures,'analyse',return_value=response), patch.object(images,'generate',side_effect=generate):
            with ThreadPoolExecutor(max_workers=3) as pool:
                futures=[pool.submit(self.threaded,lambda: pictures.run_next(self.owner.pk)) for _ in rows]
                try:
                    self.assertTrue(both.wait(12),'Two distinct provider calls must overlap.')
                    self.assertEqual(len(set(entered)),2)
                    self.assertEqual(LemmaImage.objects.filter(status='waiting').count(),1)
                    self.assertEqual(capacity.active(self.owner.pk).count(),2)
                finally: release.set()
                for future in futures: future.result(timeout=20)
            self.assertEqual(LemmaImage.objects.filter(status='ready').count(),2)
            with patch.object(pictures,'analyse') as replay:
                for row in LemmaImage.objects.filter(status='ready'): pictures.run(row.pk,row.revision)
                replay.assert_not_called()
        self.assertEqual(AIUsageCharge.objects.count(),4)
        self.assertEqual(len(entered),2)
