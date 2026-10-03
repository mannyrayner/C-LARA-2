import base64
from datetime import timedelta
from decimal import Decimal
import io
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
import uuid
import zipfile

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from PIL import Image

from community_dictionary import image_generation as images
from community_dictionary.models import Contribution, Dictionary, Entry, ImageStudy, Membership, Participation
from community_dictionary.participation import restore_all, withdraw_all
from community_dictionary.services import accept
from community_dictionary.storage import path_for, write_upload
from projects.models import AIUsageCharge, CreditAccount, Profile


@override_settings(OPENAI_API_KEY='test-key-not-real', CREDITS_ENABLED=False,
    COMMUNITY_DICTIONARY_IMAGE_MODEL='gpt-image-2.5-sunburst',
    COMMUNITY_DICTIONARY_IMAGE_DAILY_LIMIT=20, COMMUNITY_DICTIONARY_IMAGE_ALLOWANCE_USD='0.50',
    PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class ImageGenerationTests(TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        configured = override_settings(COMMUNITY_DICTIONARY_MEDIA_ROOT=Path(temporary.name))
        configured.enable(); self.addCleanup(configured.disable)
        User = get_user_model()
        self.owner = User.objects.create_user('owner', password='fixture-only')
        self.editor = User.objects.create_user('editor', password='fixture-only')
        self.member = User.objects.create_user('member', password='fixture-only')
        self.outsider = User.objects.create_user('outsider', password='fixture-only')
        self.dictionary = Dictionary.objects.create(owner=self.owner, name='Swedish', language='Swedish',
            explanation_language='English', image_generation_enabled=True)
        Membership.objects.create(dictionary=self.dictionary, user=self.editor, role='editor', accepted=True)
        Membership.objects.create(dictionary=self.dictionary, user=self.member, accepted=True)
        self.entry = Entry.objects.create(dictionary=self.dictionary, created_by=self.owner,
            word='SECRET_NOT_IN_PROMPT', meaning='SECRET_TRANSLATION')
        out = io.BytesIO(); Image.new('RGB', (30, 30), '#6b9587').save(out, 'PNG')
        self.png = out.getvalue()
        self.style = Contribution.objects.create(
            entry=Entry.objects.create(dictionary=self.dictionary, created_by=self.owner, archived=True),
            author=self.owner, kind='image', status='accepted', body='Warm watercolour, plain backgrounds',
            label='Dictionary image style', provenance={'origin':'generated', 'role':'dictionary_style'},
            **write_upload((self.png, 'image/png', '.png'), self.dictionary.pk, []))
        self.dictionary.image_style = self.style; self.dictionary.save()
        self.sdk = MagicMock()
        self.sdk.__enter__.return_value = self.sdk
        self.sdk.images.generate.return_value = self.response()
        patched = patch('community_dictionary.image_generation._openai_client', return_value=self.sdk)
        self.make_client = patched.start(); self.addCleanup(patched.stop)
        self.client.force_login(self.owner)

    def response(self, image=None):
        return SimpleNamespace(data=[SimpleNamespace(b64_json=base64.b64encode(image or self.png).decode())],
            usage=SimpleNamespace(input_tokens=100, output_tokens=2000, total_tokens=2100))

    def url(self, name, *args):
        return reverse('community_dictionary:'+name, args=[self.dictionary.pk, *args])

    def generate(self, *, style=False, token=None, **extra):
        self.dictionary.refresh_from_db()
        data = {'submission_id': str(token or uuid.uuid4()), 'style_id': self.dictionary.image_style_id or 0,
            'policy_revision': self.dictionary.image_generation_revision, 'subject':'A teapot on a table', 'ai_consent':'on'}
        if style:
            data['style_description'] = 'Clear line drawing with soft colours'
        data.update(extra)
        return self.client.post(self.url('image-style') if style else self.url('image-start', self.entry.pk), data)

    def latest(self):
        return ImageStudy.objects.latest('created_at')

    def save(self, study=None, **extra):
        study = study or self.latest()
        return self.client.post(self.url('image-action', study.pk), {'action':'save', 'consent':'on', 'publish_now':'on', **extra})

    def test_style_first_then_entry_preview_save_and_labels(self):
        self.dictionary.image_style = None; self.dictionary.save()
        page = self.client.get(self.url('image-start', self.entry.pk))
        self.assertContains(page, 'Set up the image style')
        self.assertEqual(self.generate(style=True).status_code, 302)
        study = self.latest()
        self.assertEqual(study.status, 'ready')
        self.assertContains(self.client.get(self.url('image-study', study.pk)), 'Approve this style')
        self.assertEqual(self.save(study).status_code, 302)
        self.dictionary.refresh_from_db()
        style = self.dictionary.image_style
        self.assertTrue(style.entry.archived)
        self.assertEqual(style.body, 'Clear line drawing with soft colours')
        self.assertEqual(images.active_style(self.dictionary), style)
        self.assertContains(self.client.get(self.url('image-style')), style.body)
        self.assertEqual(self.generate().status_code, 302)
        self.assertEqual(self.save().status_code, 302)
        picture = self.latest().saved_contribution
        self.assertEqual((picture.entry_id, picture.status, picture.shared_from_id), (self.entry.pk, 'accepted', style.pk))
        self.assertEqual(picture.provenance['origin'], 'generated')
        self.assertContains(self.client.get(self.url('entry', self.entry.pk)), 'AI-generated picture')
        self.assertContains(self.client.get(self.url('dictionary')), 'AI-generated picture')
        self.assertContains(self.client.get(self.url('my-content')), 'Dictionary image style')

    def test_off_by_default_and_member_ui_has_no_generation_controls(self):
        self.assertFalse(Dictionary(owner=self.owner).image_generation_enabled)
        self.client.force_login(self.member)
        for name, args in [('dictionary', ()), ('entry', (self.entry.pk,))]:
            self.assertNotContains(self.client.get(self.url(name, *args)), 'Generate a picture')
        self.assertEqual(self.generate().status_code, 404)
        self.client.force_login(self.owner)
        self.dictionary.image_generation_enabled=False; self.dictionary.save()
        self.assertEqual(self.generate().status_code, 403)
        self.assertNotContains(self.client.get(self.url('entry', self.entry.pk)), 'Generate a picture')
        self.sdk.images.generate.assert_not_called()

    def test_scoped_permissions_inactive_and_cross_dictionary_entries(self):
        self.client.force_login(self.outsider); self.assertEqual(self.generate().status_code, 404)
        self.client.force_login(self.editor)
        Membership.objects.filter(user=self.editor).update(status='inactive')
        self.assertEqual(self.generate().status_code, 404)
        self.client.force_login(self.owner)
        other = Dictionary.objects.create(owner=self.owner, name='Other', language='Italian')
        target = Entry.objects.create(dictionary=other, created_by=self.owner)
        self.assertEqual(self.client.get(self.url('image-start', target.pk)).status_code, 404)
        self.sdk.images.generate.assert_not_called()

    def test_explicit_outbound_consent_and_style_snapshot_required(self):
        self.assertEqual(self.generate(ai_consent='').status_code, 200)
        self.assertEqual(self.generate(style_id=999999).status_code, 200)
        self.assertEqual(self.generate(policy_revision=99).status_code, 200)
        self.sdk.images.generate.assert_not_called()

    def test_exact_text_only_api_request_and_no_automatic_retries(self):
        self.generate()
        args = self.sdk.images.generate.call_args.kwargs
        self.assertEqual(set(args), {'model', 'prompt', 'quality', 'size', 'output_format'})
        self.assertEqual(args['model'], 'gpt-image-2.5-sunburst')
        self.assertEqual((args['quality'], args['size']), ('high', '1024x1024'))
        self.assertIn(self.style.body, args['prompt'])
        self.assertIn('A teapot on a table', args['prompt'])
        self.assertNotIn('SECRET', args['prompt'])
        self.assertEqual(self.make_client.call_args.kwargs['max_retries'], 0)
        self.assertEqual(self.latest().cost_usd, Decimal('0.060500'))

    def test_duplicate_generate_and_save_make_one_call_charge_and_contribution(self):
        token=uuid.uuid4(); first=self.generate(token=token); second=self.generate(token=token)
        self.assertEqual(first.url, second.url)
        self.assertEqual(self.sdk.images.generate.call_count, 1)
        self.assertEqual(AIUsageCharge.objects.count(), 1)
        self.save(); self.save()
        self.assertEqual(self.entry.contributions.filter(kind='image').count(), 1)
        self.assertEqual(self.generate(token=token, subject='Different paid picture').status_code, 200)
        self.assertEqual(self.sdk.images.generate.call_count, 1)

    def test_private_preview_requires_requester_and_is_not_publicly_stored(self):
        self.generate(); study=self.latest()
        response=self.client.get(self.url('image-media', study.pk))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Cache-Control'], 'private, no-store'); response.close()
        self.assertTrue(path_for(study.file_path).is_file())
        self.assertFalse(self.entry.contributions.exists())
        self.client.force_login(self.editor)
        for name in ('image-study','image-media'):
            self.assertEqual(self.client.get(self.url(name, study.pk)).status_code, 404)
        self.assertEqual(self.save(study).status_code, 404)

    def test_save_needs_review_and_can_leave_picture_pending(self):
        self.generate()
        self.assertEqual(self.save(consent='').status_code, 200)
        self.assertFalse(self.entry.contributions.exists())
        self.assertEqual(self.save(publish_now='').status_code, 302)
        part=self.latest().saved_contribution
        self.assertEqual(part.status, 'pending')
        accept(part,self.owner); part.refresh_from_db()
        self.assertEqual(part.status, 'accepted')

    def test_existing_picture_remains_selected(self):
        old=Contribution.objects.create(entry=self.entry,author=self.owner,kind='image',status='accepted')
        self.entry.selected_image=old;self.entry.save()
        self.generate(); self.save()
        self.entry.refresh_from_db()
        self.assertEqual(self.entry.selected_image_id, old.pk)

    def test_replacing_style_is_optimistic_and_does_not_restyle_saved_images(self):
        self.generate(); self.save(); picture=self.latest().saved_contribution
        self.generate(style=True); first=self.latest()
        self.generate(style=True); second=self.latest()
        self.assertEqual(self.save(first).status_code, 302)
        self.assertEqual(self.save(second).status_code, 409)
        picture.refresh_from_db()
        self.assertEqual(picture.shared_from_id,self.style.pk)

    def test_style_change_blocks_older_entry_preview(self):
        self.generate(); old=self.latest()
        self.generate(style=True); self.save()
        self.assertEqual(self.save(old).status_code, 409)

    def test_disabled_during_call_drops_result_but_records_cost(self):
        def respond(**kwargs):
            Dictionary.objects.filter(pk=self.dictionary.pk).update(image_generation_enabled=False,
                image_generation_revision=1)
            return self.response()
        self.sdk.images.generate.side_effect=respond
        self.generate(); study=self.latest()
        self.assertEqual(study.status,'discarded')
        self.assertEqual((study.file_path,study.prompt),('',''))
        self.assertEqual(AIUsageCharge.objects.count(),1)

    def test_departure_during_call_cannot_be_undone_by_late_result(self):
        self.client.force_login(self.editor)
        def respond(**kwargs):
            withdraw_all(self.editor,self.dictionary.pk,0)
            restore_all(self.editor,self.dictionary.pk,1)
            return self.response()
        self.sdk.images.generate.side_effect=respond
        self.generate(); study=self.latest()
        self.assertEqual(study.status,'discarded')
        self.assertEqual(study.file_path,'')
        self.assertEqual(self.save(study).status_code,409)

    def test_style_withdrawal_hides_dependents_and_cancels_other_users_drafts(self):
        self.client.force_login(self.editor)
        self.generate();self.save(); picture=self.latest().saved_contribution
        self.generate(); preview=self.latest(); preview_path=preview.file_path
        with self.captureOnCommitCallbacks(execute=True):
            withdraw_all(self.owner,self.dictionary.pk,0,successor_id=self.editor.pk)
        self.style.refresh_from_db();picture.refresh_from_db();preview.refresh_from_db()
        self.assertTrue(self.style.entry.dictionary.personal)
        self.assertTrue(picture.entry.dictionary.personal)
        self.assertEqual((preview.status,preview.prompt,preview.style_description),('discarded','',''))
        self.assertFalse(path_for(preview_path).exists())
        self.assertEqual(self.client.get(self.url('image-media',preview.pk)).status_code,404)
        self.dictionary.refresh_from_db();self.assertIsNone(images.active_style(self.dictionary))
        restore_all(self.owner,self.dictionary.pk,1)
        picture.refresh_from_db();self.style.refresh_from_db()
        self.assertEqual((picture.entry_id,picture.status),(self.entry.pk,'accepted'))
        self.assertEqual(images.active_style(self.dictionary),self.style)

    def test_overlapping_style_and_requester_withdrawals_do_not_release_early(self):
        self.client.force_login(self.editor);self.generate();self.save();picture=self.latest().saved_contribution
        withdraw_all(self.editor,self.dictionary.pk,0)
        withdraw_all(self.owner,self.dictionary.pk,0,successor_id=self.member.pk)
        restore_all(self.editor,self.dictionary.pk,1)
        picture.refresh_from_db();self.assertTrue(picture.entry.dictionary.personal)
        restore_all(self.owner,self.dictionary.pk,1)
        picture.refresh_from_db();self.assertEqual(picture.entry_id,self.entry.pk)

    def test_archived_entry_and_inactive_requester_cannot_save_preview(self):
        self.generate();study=self.latest()
        self.entry.archived=True;self.entry.save()
        self.assertEqual(self.save(study).status_code,409)
        self.entry.archived=False;self.entry.save()
        self.client.force_login(self.editor);self.generate();study=self.latest()
        Membership.objects.filter(user=self.editor).update(status='inactive')
        self.assertEqual(self.save(study).status_code,404)

    def test_failed_call_is_not_repeated_on_refresh_or_replay(self):
        self.sdk.images.generate.side_effect=TimeoutError()
        token=uuid.uuid4();self.generate(token=token);study=self.latest()
        self.assertEqual(study.status,'failed'); self.assertIsNone(study.cost_usd)
        self.generate(token=token);self.client.get(self.url('image-study',study.pk))
        self.assertEqual(self.sdk.images.generate.call_count,1)
        self.assertEqual(self.save(study).status_code,409)

    def test_unusable_image_still_has_usage_and_url_only_response_is_not_fetched(self):
        self.sdk.images.generate.return_value=self.response(b'not an image')
        self.generate();self.assertEqual(self.latest().status,'failed')
        self.assertEqual(self.latest().cost_usd,Decimal('0.060500'))
        self.sdk.images.generate.return_value=SimpleNamespace(data=[SimpleNamespace(b64_json=None,url='https://example.invalid/private')])
        with patch('core.ai_api.urllib.request.urlopen') as fetch:
            self.generate();fetch.assert_not_called()
        self.assertEqual(self.latest().status,'failed')

    def test_daily_limits_cover_style_samples_and_failed_calls(self):
        self.generate(style=True)
        with override_settings(COMMUNITY_DICTIONARY_IMAGE_DAILY_LIMIT=1):
            self.assertEqual(self.generate().status_code,200)
            self.client.force_login(self.editor)
            self.assertEqual(self.generate().status_code,200)
        self.assertEqual(self.sdk.images.generate.call_count,1)

    def test_in_progress_attempt_blocks_new_paid_request(self):
        self.generate();study=self.latest();study.status='processing';study.save()
        self.assertEqual(self.generate().status_code,200)
        self.assertEqual(self.sdk.images.generate.call_count,1)

    def test_csrf_required_and_get_does_not_mutate(self):
        client=Client(enforce_csrf_checks=True);client.force_login(self.owner)
        self.assertEqual(client.post(self.url('image-style'),{}).status_code,403)
        self.generate();study=self.latest()
        self.assertEqual(client.get(self.url('image-action',study.pk)).status_code,405)
        self.assertEqual(client.post(self.url('image-action',study.pk),{'action':'save','consent':'on'}).status_code,403)

    def test_expiry_discards_only_previews_not_saved_media(self):
        self.generate();self.save();picture=self.latest().saved_contribution
        self.generate();preview=self.latest();file=preview.file_path
        ImageStudy.objects.update(expires_at=timezone.now()-timedelta(seconds=1))
        self.assertEqual(self.client.get(self.url('image-media',preview.pk)).status_code,404)
        call_command('expire_photo_studies',stdout=io.StringIO())
        self.assertFalse(path_for(file).exists())
        self.assertTrue(path_for(picture.file_path).is_file())

    def test_dictionary_export_includes_shared_style_and_excludes_private_previews(self):
        self.generate(); preview=self.latest()
        response=self.client.get(self.url('export'))
        with zipfile.ZipFile(io.BytesIO(b''.join(response.streaming_content))) as archive:
            self.assertNotIn('media/'+preview.file_path,archive.namelist())
            records=json.loads(archive.read('records.json'))
            row=next(r for r in records if r['model']=='community_dictionary.dictionary')
            self.assertEqual(row['fields']['image_style'],self.style.pk)
        response.close()
        withdraw_all(self.owner,self.dictionary.pk,0,successor_id=self.editor.pk)
        self.client.force_login(self.editor)
        response=self.client.get(self.url('export'))
        with zipfile.ZipFile(io.BytesIO(b''.join(response.streaming_content))) as archive:
            records=json.loads(archive.read('records.json'))
            row=next(r for r in records if r['model']=='community_dictionary.dictionary')
            self.assertIsNone(row['fields']['image_style'])
            self.assertNotIn(self.style.body,archive.read('records.json').decode())
        response.close()

    def test_credit_gate_and_charge_once_from_provider_tokens(self):
        with override_settings(CREDITS_ENABLED=True):
            self.assertEqual(self.generate().status_code,200)
            self.sdk.images.generate.assert_not_called()
            CreditAccount.objects.filter(user=self.owner).update(balance_usd=Decimal('1'))
            token=uuid.uuid4();self.generate(token=token);self.generate(token=token)
            self.assertEqual(CreditAccount.objects.get(user=self.owner).balance_usd,Decimal('0.9395'))
            self.assertEqual(AIUsageCharge.objects.count(),1)

    def test_personal_key_not_charged_to_clara_and_unknown_model_no_fallback(self):
        Profile.objects.create(user=self.owner, use_personal_openai_key=True,
            openai_api_key='personal-test-not-real')
        with override_settings(CREDITS_ENABLED=True):
            self.generate()
        self.assertTrue(self.latest().personal_key)
        self.assertFalse(AIUsageCharge.objects.exists())
        with override_settings(COMMUNITY_DICTIONARY_IMAGE_MODEL='not-configured'):
            self.assertEqual(self.generate().status_code,200)
        self.assertEqual(self.sdk.images.generate.call_count,1)
