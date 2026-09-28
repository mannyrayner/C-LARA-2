import base64
from datetime import timedelta
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import uuid
from unittest.mock import patch
import zipfile

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from PIL import Image

from community_dictionary import photo_ai
from community_dictionary.models import Contribution, Dictionary, Entry, Membership, PhotoStudy
from community_dictionary.storage import path_for
from community_dictionary.tests.test_workflow import picture
from projects.models import AIUsageCharge, CreditAccount, Profile


def response(outcome='candidate'):
    result = {'outcome': outcome, 'feedback': 'This looks like a teapot. Is that what you mean?',
              'word': 'la teiera', 'meaning': 'teapot', 'language_code': 'it'}
    if outcome != 'candidate':
        result.update(feedback='Please photograph one object more closely.', word='', meaning='', language_code='')
    return SimpleNamespace(status='completed', output_text=json.dumps(result),
        usage=SimpleNamespace(input_tokens=1200, output_tokens=160, total_tokens=1360))


@override_settings(OPENAI_API_KEY='test-only', CREDITS_ENABLED=False)
class PhotoLearningTests(TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        overrides = override_settings(COMMUNITY_DICTIONARY_MEDIA_ROOT=Path(self.temp.name)/'private',
            MEDIA_ROOT=Path(self.temp.name)/'public', PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
        overrides.enable(); self.addCleanup(overrides.disable)
        self.owner = get_user_model().objects.create_user('photo-owner', password='test')
        self.member = get_user_model().objects.create_user('photo-member', password='test')
        self.outsider = get_user_model().objects.create_user('photo-outsider', password='test')
        self.dictionary = Dictionary.objects.create(owner=self.owner, name='Our Italian', language='Italian', explanation_language='English', photo_ai_enabled=True)
        Membership.objects.create(dictionary=self.dictionary, user=self.member, accepted=True)
        self.client.force_login(self.member)
        self.mock = patch('community_dictionary.photo_ai.analyse', return_value=response()).start()
        self.addCleanup(patch.stopall)

    def url(self, name, study=None):
        return reverse('community_dictionary:'+name, args=[self.dictionary.pk]+([study.pk] if study else []))

    def upload(self, token=None, **extra):
        return self.client.post(self.url('photo-start'), {'submission_id': token or uuid.uuid4(), 'photo': picture(), 'ai_consent': 'on', **extra})

    def study(self):
        result = self.upload()
        self.assertEqual(result.status_code, 302)
        return PhotoStudy.objects.latest('created_at')

    def act(self, study, action, **kwargs):
        return self.client.post(self.url('photo-action', study), {'action': action, **kwargs})

    def test_confirmation_optional_save_and_review(self):
        study = self.study()
        self.assertEqual(Entry.objects.count(), 0)
        page = self.client.get(self.url('photo-study', study))
        self.assertContains(page, 'Is that what you mean?')
        self.assertNotContains(page, 'la teiera')
        self.assertEqual(self.act(study, 'save', word='la teiera', consent='on').status_code, 409)
        self.act(study, 'confirm')
        self.assertContains(self.client.get(self.url('photo-study', study)), 'la teiera')
        with self.captureOnCommitCallbacks(execute=True):
            saved = self.act(study, 'save', word='una teiera', meaning='a teapot', consent='on', publish_now='on')
        self.assertEqual(saved.status_code, 302)
        entry = Entry.objects.get()
        self.assertEqual(entry.word, '')  # Member cannot publish, even with a forged checkbox.
        self.assertEqual(entry.contributions.count(), 2)
        wording = entry.contributions.get(kind='text')
        self.assertEqual(wording.word, 'una teiera')
        self.assertEqual(wording.provenance['proposed_word'], 'la teiera')
        self.assertEqual(wording.status, 'pending')
        self.assertFalse(path_for(study.file_path).exists())
        self.assertEqual(self.act(study, 'save', word='duplicate', consent='on').url, saved.url)
        self.assertEqual(Entry.objects.count(), 1)
        self.assertEqual(self.mock.call_count, 1)

    def test_owner_can_publish_and_export_provenance(self):
        self.client.force_login(self.owner)
        study = self.study(); self.act(study, 'confirm')
        self.act(study, 'save', word='la teiera', meaning='teapot', consent='on', publish_now='on')
        self.assertEqual(Entry.objects.get().word, 'la teiera')
        exported = self.client.get(self.url('export'))
        with zipfile.ZipFile(io.BytesIO(b''.join(exported.streaming_content))) as archive:
            self.assertEqual(json.loads(archive.read('manifest.json'))['origin'], 'mixed')
            records = json.loads(archive.read('records.json'))
            self.assertFalse(any(r['model'] == 'community_dictionary.photostudy' for r in records))
            self.assertTrue(any(r['fields'].get('provenance', {}).get('origin') == 'ai-assisted' for r in records))

    def test_replay_makes_one_provider_call_and_usage_record(self):
        token = uuid.uuid4()
        first, second = self.upload(token), self.upload(token)
        self.assertEqual(first.url, second.url)
        self.assertEqual(self.mock.call_count, 1)
        self.assertEqual(PhotoStudy.objects.count(), 1)
        self.assertEqual(AIUsageCharge.objects.filter(operation='community_photo').count(), 1)
        self.assertEqual(self.upload(token, ai_consent='').status_code, 200)
        self.assertEqual(self.mock.call_count, 1)

    def test_policy_consent_membership_and_csrf(self):
        self.assertEqual(self.upload(ai_consent='').status_code, 200)
        self.assertEqual(PhotoStudy.objects.count(), 0)
        csrf = Client(enforce_csrf_checks=True); csrf.force_login(self.member)
        self.assertEqual(csrf.post(self.url('photo-start'), {}).status_code, 403)
        self.dictionary.photo_ai_enabled = False; self.dictionary.save()
        self.assertEqual(self.upload().status_code, 403)
        self.client.force_login(self.outsider)
        self.assertEqual(self.upload().status_code, 404)
        self.mock.assert_not_called()

    def test_draft_private_even_from_dictionary_owner_and_revoked_member(self):
        study = self.study()
        media = self.client.get(self.url('photo-media', study))
        self.assertEqual(media.status_code, 200)
        self.assertIn('no-store', media['Cache-Control']); media.close()
        self.client.force_login(self.owner)
        for endpoint in ['photo-study', 'photo-media']:
            self.assertEqual(self.client.get(self.url(endpoint, study)).status_code, 404)
        self.assertEqual(self.act(study, 'confirm').status_code, 404)
        self.client.force_login(self.member)
        Membership.objects.filter(user=self.member).delete()
        self.assertEqual(self.client.get(self.url('photo-media', study)).status_code, 404)

    def test_ambiguous_unsupported_and_failed_never_save(self):
        for outcome in ['unclear', 'unsupported']:
            self.mock.return_value = response(outcome)
            study = self.study()
            self.assertEqual(study.status, 'unclear')
            self.assertEqual(self.act(study, 'confirm').status_code, 409)
            self.assertEqual(self.act(study, 'save', word='guess', consent='on').status_code, 409)
        self.mock.side_effect = TimeoutError('must not appear in response')
        study = self.study()
        self.assertEqual(study.status, 'failed')
        self.assertNotContains(self.client.get(self.url('photo-study', study)), 'must not appear')
        self.assertEqual(Entry.objects.count(), 0)

    def test_invalid_result_still_accounts_for_returned_usage(self):
        bad = response(); bad.output_text = '{invalid'
        self.mock.return_value = bad
        study = self.study()
        self.assertEqual(study.status, 'failed')
        self.assertEqual(study.usage['total_tokens'], 1360)
        self.assertEqual(AIUsageCharge.objects.count(), 1)

    @override_settings(COMMUNITY_DICTIONARY_PHOTO_DAILY_LIMIT=1)
    def test_quota_survives_discard_and_blocks_provider(self):
        study = self.study()
        with self.captureOnCommitCallbacks(execute=True): self.act(study, 'discard')
        self.assertFalse(path_for(study.file_path).exists())
        self.assertContains(self.upload(), 'daily photo-analysis limit')
        self.assertEqual(self.mock.call_count, 1)

    def test_expiry_denies_access_and_cleanup_preserves_saved_media(self):
        study = self.study(); self.act(study, 'confirm')
        self.act(study, 'save', word='la teiera', consent='on')
        saved_file = Contribution.objects.get(kind='image').file_path
        other = self.study()
        PhotoStudy.objects.update(expires_at=timezone.now()-timedelta(seconds=1))
        self.assertEqual(self.client.get(self.url('photo-media', other)).status_code, 404)
        call_command('expire_photo_studies', stdout=io.StringIO())
        self.assertEqual(PhotoStudy.objects.count(), 0)
        self.assertFalse(path_for(other.file_path).exists())
        self.assertTrue(path_for(saved_file).exists())

    def test_save_failure_rolls_back_records_and_new_files(self):
        study = self.study(); self.act(study, 'confirm')
        before = set(Path(self.temp.name).rglob('*.jpg'))
        with patch('community_dictionary.photo_views.PhotoStudy.save', side_effect=RuntimeError('test')):
            with self.assertRaises(RuntimeError): self.act(study, 'save', word='word', consent='on')
        study.refresh_from_db()
        self.assertEqual(study.status, 'confirmed')
        self.assertEqual(Entry.objects.count(), 0)
        self.assertEqual(set(Path(self.temp.name).rglob('*.jpg')), before)

    def test_same_receipt_with_changed_photo_does_not_call_again(self):
        token = uuid.uuid4(); self.upload(token)
        changed = picture(); changed.name = 'changed.png'
        raw = io.BytesIO(); Image.new('RGB', (50, 30), 'red').save(raw, 'PNG')
        from django.core.files.uploadedfile import SimpleUploadedFile
        page = self.client.post(self.url('photo-start'), {'submission_id': token,
            'ai_consent': 'on', 'photo': SimpleUploadedFile('red.png', raw.getvalue())})
        self.assertContains(page, 'saved submission has changed')
        self.assertEqual(self.mock.call_count, 1)

    @override_settings(COMMUNITY_DICTIONARY_PHOTO_MODEL='unpriced-model')
    def test_unpriced_model_fails_closed(self):
        self.assertContains(self.upload(), 'configure pricing')
        self.mock.assert_not_called()

    def test_owner_policy_cannot_be_changed_by_member(self):
        response = self.client.post(self.url('people'), {'action':'settings', 'name':'Our Italian',
            'language':'Italian', 'explanation_language':'English', 'text_direction':'auto'})
        self.assertEqual(response.status_code, 404)
        self.dictionary.refresh_from_db(); self.assertTrue(self.dictionary.photo_ai_enabled)

    @override_settings(CREDITS_ENABLED=True)
    def test_credit_gate_and_single_charge(self):
        self.assertContains(self.upload(), 'balance is too low')
        self.mock.assert_not_called()
        CreditAccount.objects.filter(user=self.member).update(balance_usd='1.0000')
        token = uuid.uuid4(); self.upload(token); self.upload(token)
        self.assertEqual(AIUsageCharge.objects.count(), 1)
        self.assertLess(CreditAccount.objects.get(user=self.member).balance_usd, 1)

    def test_empty_personal_key_never_falls_back_to_server_key(self):
        profile, _ = Profile.objects.get_or_create(user=self.member)
        profile.use_personal_openai_key = True; profile.openai_api_key = ''; profile.save()
        self.assertContains(self.upload(), 'Add your OpenAI API key')
        self.mock.assert_not_called()

    def test_personal_key_not_charged_platform_credits(self):
        profile, _ = Profile.objects.get_or_create(user=self.member)
        profile.use_personal_openai_key = True; profile.openai_api_key = 'personal-test'; profile.save()
        study = self.study()
        self.assertTrue(study.personal_key)
        self.assertEqual(AIUsageCharge.objects.count(), 0)
        self.assertEqual(self.mock.call_args.kwargs['api_key'], 'personal-test')

    def test_stuck_attempt_is_read_only_and_never_retried(self):
        study = self.study()
        PhotoStudy.objects.filter(pk=study.pk).update(status='processing', created_at=timezone.now()-timedelta(minutes=2), result={})
        self.assertContains(self.client.get(self.url('photo-study', study)), 'could not be recovered')
        self.assertEqual(self.mock.call_count, 1)


class ProviderContractTests(TestCase):
    def test_single_bounded_request_and_metadata_free_image(self):
        stream = io.BytesIO(); Image.new('RGB', (2000, 1500)).save(stream, 'JPEG')
        with patch('community_dictionary.photo_ai._openai_client') as sdk:
            photo_ai.analyse(stream.getvalue(), language='Italian', explanation_language='Swedish', model='gpt-6-sol', api_key='test')
            self.assertEqual(sdk.call_args.kwargs['max_retries'], 0)
            call = sdk.return_value.__enter__.return_value.responses.create.call_args.kwargs
            self.assertFalse(call['store']); self.assertNotIn('tools', call)
            self.assertTrue(call['text']['format']['strict'])
            self.assertIn('Swedish', call['input'][0]['content'][0]['text'])
            image = Image.open(io.BytesIO(base64.b64decode(call['input'][0]['content'][1]['image_url'].split(',')[1])))
            self.assertEqual(image.size, (1024, 768)); self.assertFalse(image.getexif())

    def test_fresh_process_loads_sdk_without_project_httpx_shadowing(self):
        # A fresh process is essential: importing httpx in an earlier test can
        # hide the startup bug. Construct the installed SDK without making a call.
        platform = Path(__file__).resolve().parents[2]
        program = '''
import os
import sys
from pathlib import Path
os.environ['DJANGO_SETTINGS_MODULE'] = 'platform_server.settings'
os.environ.pop('DJANGO_Q_USE_REAL', None)
import django
django.setup()
from django.urls import get_resolver
get_resolver().check()
assert 'openai' not in sys.modules, 'URL loading must not import the optional SDK'
from community_dictionary.photo_ai import _openai_client
original_path = sys.path.copy()
with _openai_client(api_key='test-only-no-request', timeout=1, max_retries=0) as client:
    assert callable(client.responses.create)
assert sys.path == original_path, 'SDK loader must restore the import path'
httpx = sys.modules.get('httpx')
if httpx is not None:
    assert hasattr(httpx, 'URL'), httpx.__file__
    assert Path(httpx.__file__).resolve() != Path('../src/httpx.py').resolve()
'''
        # No network call is made. Host proxy settings must not require optional
        # SOCKS packages just to construct a client during this import test.
        env = {key: value for key, value in os.environ.items()
               if key.lower() not in {'http_proxy', 'https_proxy', 'all_proxy'}}
        command = [sys.executable] + (['-E'] if sys.flags.ignore_environment else []) + ['-c', program]
        result = subprocess.run(command, cwd=platform,
            env=env, capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_rejects_refusal_incomplete_and_malformed_values(self):
        cases = [response(), response(), response(), response()]
        cases[0].status = 'incomplete'
        cases[1].output_text = ''
        data = json.loads(cases[2].output_text); data['word'] = ['word']; cases[2].output_text = json.dumps(data)
        data = json.loads(cases[3].output_text); data['language_code'] = '<script>'; cases[3].output_text = json.dumps(data)
        for case in cases:
            with self.assertRaises(ValueError): photo_ai.parse_result(case)
