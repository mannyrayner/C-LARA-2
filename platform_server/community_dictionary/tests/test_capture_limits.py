"""Allowance approval, rolling enforcement and cost assumptions; no paid calls."""
from datetime import timedelta
from decimal import Decimal
import uuid
from unittest.mock import patch
from django.core import signing
from django.test import Client, TestCase, override_settings
from django.utils import timezone
from community_dictionary import capture, capture_limits, image_copy
from community_dictionary.models import Dictionary, Membership, PictureCapture, Event, Participation
from community_dictionary.services import Conflict
from projects.models import AIUsageCharge, CreditAccount
from . import test_picture_capture as base


@override_settings(OPENAI_API_KEY='test-only', CREDITS_ENABLED=False,
    PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class CaptureLimitTests(TestCase):
    setUp=base.PictureCaptureTests.setUp
    url=base.PictureCaptureTests.url
    start=base.PictureCaptureTests.start
    ready=base.PictureCaptureTests.ready
    action=base.PictureCaptureTests.action
    publish=base.PictureCaptureTests.publish
    word=base.PictureCaptureTests.word
    image=base.PictureCaptureTests.image

    def preview(self, limit=50):
        self.client.force_login(self.owner)
        page=self.client.post(self.url('capture-limit'), {'action':'preview','daily_limit':limit})
        self.assertEqual(page.status_code,200)
        return page.context['estimate'],page

    def confirm(self, estimate, **extra):
        return self.client.post(self.url('capture-limit'), {'action':'confirm','token':estimate['token'],'approve':'on',**extra})

    def attempt(self, user=None, dictionary=None, age=0, status='failed'):
        return PictureCapture.objects.create(dictionary=dictionary or self.d,user=user or self.user,
            expires_at=timezone.now()+timedelta(days=1),created_at=timezone.now()-timedelta(hours=age),status=status)

    def submit(self, token=None):
        return self.client.post(self.url('capture-start'),{'submission_id':token or uuid.uuid4(),
            'photo':base.picture(),'description':'A cat.', 'input_language':'English',
            'input_mode':'text','voice':'marin','ai_consent':'on'})

    def test_settings_has_preview_and_confirmation_changes_only_allowance(self):
        self.client.force_login(self.owner)
        self.assertContains(self.client.get(self.url('settings')),'Preview daily cost')
        estimate,page=self.preview()
        self.d.refresh_from_db();self.assertEqual(self.d.capture_daily_limit,10)
        self.assertContains(page,'not a spending cap')
        self.assertContains(page,'up to six new words with audio')
        self.assertEqual(estimate['daily_estimate'],Decimal(estimate['per_request'])*50)
        self.assertEqual(self.confirm(estimate).status_code,302)
        self.assertEqual(self.confirm(estimate).status_code,302)
        self.d.refresh_from_db();self.assertEqual(self.d.capture_daily_limit,50)
        self.assertEqual(self.d.capture_revision,0)
        self.assertEqual(Event.objects.filter(action='capture_allowance_changed').count(),1)
        self.assertFalse(AIUsageCharge.objects.exists());self.ai.assert_not_called();self.tts.assert_not_called()

    def test_confirmation_required_signed_and_owner_scoped(self):
        estimate,_=self.preview()
        self.assertEqual(self.confirm(estimate,approve='').status_code,400)
        self.assertEqual(self.confirm(estimate,token=estimate['token']+'x').status_code,409)
        # Posted daily_limit cannot replace the signed approved value.
        self.assertEqual(self.confirm(estimate,daily_limit=999).status_code,302)
        self.d.refresh_from_db();self.assertEqual(self.d.capture_daily_limit,50)
        other=Dictionary.objects.create(owner=self.owner,name='Other',language='Swedish')
        response=self.client.post('/community-dictionaries/%s/settings/picture-allowance/'%other.pk,
            {'action':'confirm','token':estimate['token'],'approve':'on'})
        self.assertEqual(response.status_code,409)
        other.refresh_from_db();self.assertEqual(other.capture_daily_limit,10)

    def test_members_editors_outsiders_and_withdrawn_owner_cannot_change(self):
        estimate,_=self.preview()
        for user,role in [(self.user,'member'),(self.user,'editor'),(self.outsider,None)]:
            if role: Membership.objects.filter(user=user,dictionary=self.d).update(role=role)
            self.client.force_login(user)
            self.assertEqual(self.client.get(self.url('capture-limit')).status_code,404)
            self.assertEqual(self.confirm(estimate).status_code,404)
        self.client.force_login(self.owner)
        Participation.objects.create(dictionary=self.d,user=self.owner,withdrawn=True)
        self.assertEqual(self.confirm(estimate).status_code,404)
        self.d.refresh_from_db();self.assertEqual(self.d.capture_daily_limit,10)

    def test_csrf_and_invalid_limits(self):
        csrf=Client(enforce_csrf_checks=True);csrf.force_login(self.owner)
        self.assertEqual(csrf.post(self.url('capture-limit'),{'action':'preview','daily_limit':20}).status_code,403)
        for limit in [0,-1,'1.5','wrong',1001]:
            self.client.force_login(self.owner)
            page=self.client.post(self.url('capture-limit'),{'action':'preview','daily_limit':limit})
            self.assertEqual(page.status_code,200)
            self.assertIsNone(page.context['estimate'])
            self.assertTrue(page.context['form'].errors)
        self.d.refresh_from_db();self.assertEqual(self.d.capture_daily_limit,10)

    def test_expired_or_changed_price_or_quota_previews_cannot_apply(self):
        estimate,_=self.preview()
        with patch('django.core.signing.time.time',return_value=timezone.now().timestamp()+601):
            self.assertEqual(self.confirm(estimate).status_code,409)
        with patch('community_dictionary.photo_ai.pricing_configuration',return_value=('changed-model',{'input':2,'output':10})):
            self.assertEqual(self.confirm(estimate).status_code,409)
        Dictionary.objects.filter(pk=self.d.pk).update(capture_daily_limit=12)
        self.assertEqual(self.confirm(estimate).status_code,409)
        self.d.refresh_from_db();self.assertEqual(self.d.capture_daily_limit,12)
        with override_settings(COMMUNITY_DICTIONARY_CAPTURE_DAILY_LIMIT=15):
            self.assertEqual(self.confirm(estimate).status_code,409)

    def test_raised_limit_admits_eleventh_request_and_replay_does_not_count_twice(self):
        for _ in range(10): self.attempt()
        self.assertContains(self.submit(),'picture-description allowance')
        estimate,_=self.preview(20);self.confirm(estimate)
        self.client.force_login(self.user)
        token=uuid.uuid4()
        self.assertEqual(self.submit(token).status_code,302)
        self.assertEqual(self.submit(token).status_code,302)
        self.assertEqual(PictureCapture.objects.count(),11)
        self.assertEqual(capture_limits.usage(self.d)['used'],11)
        self.ai.assert_not_called();self.tts.assert_not_called()

    def test_rolling_shared_count_includes_failed_and_discarded_but_not_old_attempts(self):
        self.attempt(user=self.owner,status='failed')
        self.attempt(status='discarded')
        self.attempt(status='saved',age=25)
        counts=capture_limits.usage(self.d)
        self.assertEqual(counts['used'],2);self.assertEqual(counts['remaining'],8)
        estimate,_=self.preview(1)
        self.assertContains(self.client.post(self.url('capture-limit'),{'action':'preview','daily_limit':1}),'already used more')
        self.confirm(estimate);self.d.refresh_from_db()
        self.assertEqual(capture_limits.usage(self.d)['remaining'],0)
        self.client.force_login(self.user)
        self.assertContains(self.submit(),'picture-description allowance')
        PictureCapture.objects.update(created_at=timezone.now()-timedelta(hours=25))
        self.assertEqual(self.submit().status_code,302)

    @override_settings(COMMUNITY_DICTIONARY_CAPTURE_DAILY_LIMIT=3)
    def test_server_and_cross_dictionary_account_ceiling_remain_enforced(self):
        other=Dictionary.objects.create(owner=self.user,name='Other',language='Swedish')
        for _ in range(3):self.attempt(dictionary=other)
        self.assertContains(self.submit(),'server limit')
        self.assertEqual(PictureCapture.objects.filter(dictionary=self.d).count(),0)
        self.assertEqual(capture_limits.effective_limit(self.d),3)
        self.client.force_login(self.owner)
        page=self.client.post(self.url('capture-limit'),{'action':'preview','daily_limit':4})
        self.assertTrue(page.context['form'].errors)

    def test_lowering_allowance_keeps_previews_and_does_not_reset_usage(self):
        s=self.ready()
        estimate,_=self.preview(1);self.confirm(estimate)
        s.refresh_from_db();self.assertEqual(s.status,'ready')
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(self.url('capture-detail',s.pk)).status_code,200)
        self.assertEqual(self.action(s,'confirm',permission='yes').status_code,302)
        self.assertEqual(PictureCapture.objects.count(),1)
        self.assertContains(self.submit(),'picture-description allowance')

    def test_cost_formula_and_warning_use_local_rates_without_needing_owner_api_key(self):
        with patch('community_dictionary.photo_ai.pricing_configuration',return_value=('configured-model',{'input':'2','output':'10'})), override_settings(CREDITS_ENABLED=True,OPENAI_API_KEY=''):
            CreditAccount.objects.update_or_create(user=self.owner,defaults={'balance_usd':Decimal('1')})
            estimate,page=self.preview(50)
            self.assertEqual(Decimal(estimate['per_request']),Decimal('.13'))
            self.assertEqual(estimate['daily_estimate'],Decimal('6.50'))
            self.assertContains(page,'US$6.50')
            self.assertContains(page,'balance may not cover')
            self.assertFalse(AIUsageCharge.objects.exists())
        self.ai.assert_not_called();self.tts.assert_not_called()

    def test_regular_settings_cannot_bypass_confirmation_and_new_copies_start_at_ten(self):
        self.client.force_login(self.owner)
        self.client.post(self.url('settings'),{'name':'Swedish','language':'Swedish','explanation_language':'English',
            'tts_enabled':'on','sentence_capture_enabled':'on','capture_daily_limit':500})
        self.d.refresh_from_db();self.assertEqual(self.d.capture_daily_limit,10)
        self.image();self.d.capture_daily_limit=50;self.d.save()
        copy=image_copy.create(self.d,self.owner,'New image-only copy')
        self.assertEqual(copy.capture_daily_limit,10)
