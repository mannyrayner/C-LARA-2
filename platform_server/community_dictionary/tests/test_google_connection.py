"""No live sign-in or network requests: recovery boundaries and error redaction."""
import io
import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
from unittest.mock import Mock, patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase, override_settings
from google.auth.exceptions import RefreshError, TransportError
from google.api_core.exceptions import ServiceUnavailable, PermissionDenied

from community_dictionary import google_tts
from community_dictionary.management.commands import community_google_tts_connect as connect


@override_settings(COMMUNITY_DICTIONARY_GOOGLE_TTS_PROJECT='community-dictionaries-tts',
                   COMMUNITY_DICTIONARY_GOOGLE_TTS_ENABLED=True)
class GoogleConnectionTests(SimpleTestCase):
    def test_refresh_failure_is_distinct_and_never_exposes_provider_message(self):
        auth=Mock();auth.refresh.side_effect=RefreshError('reauth needed PRIVATE_TOKEN')
        with patch.object(google_tts,'credentials',return_value=auth), \
             patch('google.cloud.texttospeech.TextToSpeechClient') as client:
            with self.assertRaises(google_tts.GoogleAccessError) as caught:
                google_tts.client()
            self.assertEqual((caught.exception.code,caught.exception.stage),('sign_in','sign-in renewal'))
            self.assertNotIn('PRIVATE_TOKEN',str(caught.exception));client.assert_not_called()

    def test_fresh_credentials_are_passed_to_client_and_timeout_is_bounded(self):
        auth=Mock()
        with patch.object(google_tts,'credentials',return_value=auth), \
             patch('google.cloud.texttospeech.TextToSpeechClient') as client:
            google_tts.client()
            client.assert_called_once_with(credentials=auth)
            auth.refresh.assert_called_once()
            self.assertEqual(auth.refresh.call_args.args[0].keywords['timeout'],30)

    def test_error_categories_hide_raw_error_details(self):
        for exc,code in [(ServiceUnavailable('PRIVATE_TOKEN'),'connection'),
                         (TransportError('PRIVATE_TOKEN'),'connection'),
                         (PermissionDenied('PRIVATE_TOKEN'),'permission'),
                         (RefreshError('serviceusage.services.use PRIVATE_TOKEN'),'permission')]:
            safe=google_tts.access_error(exc,'test')
            self.assertEqual(safe.code,code);self.assertNotIn('PRIVATE_TOKEN',str(safe))

    def test_voice_check_supports_mixed_english_locales_and_closes_transport(self):
        connection=Mock()
        connection.list_voices.return_value.voices=[SimpleNamespace(name=n,language_codes=[google_tts.voice_locale(n)])
            for n in ['en-US-Wavenet-F','en-GB-Neural2-F']]
        with patch.object(google_tts,'client',return_value=connection):
            google_tts.check_access(SimpleNamespace(is_active=True,is_staff=True),'English',
                selected_voices=['en-US-Wavenet-F','en-GB-Neural2-F'])
        connection.list_voices.assert_called_once_with(request={},retry=None,timeout=30)
        connection.transport.close.assert_called_once()

    def test_interactive_login_is_disabled_on_aws(self):
        with patch.object(connect,'windows_host',return_value=False), patch.object(connect.subprocess,'run') as run:
            with self.assertRaises(CommandError):call_command('community_google_tts_connect',stdout=io.StringIO())
            run.assert_not_called()

    def test_launcher_uses_exact_credential_directory_for_forced_login_and_checks_voices(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'application_default_credentials.json'
            path.write_text(json.dumps({'type':'authorized_user','refresh_token':'PRIVATE_TOKEN'}))
            connection=Mock();connection.list_voices.return_value.voices=[SimpleNamespace(name=n)
                for n in ['en-GB-Wavenet-F','en-GB-Neural2-F']]
            output=io.StringIO()
            with patch.object(connect,'windows_host',return_value=True), patch.object(connect,'find_gcloud',return_value='gcloud.cmd'), \
                 patch.object(google_tts,'credential_path',return_value=path), patch.object(google_tts,'client',return_value=connection), \
                 patch.object(connect.subprocess,'run',return_value=SimpleNamespace(returncode=0)) as run, \
                 patch.dict('os.environ',{'PYTHONHOME':'bad','PYTHONPATH':'bad','GOOGLE_APPLICATION_CREDENTIALS':'legacy'}):
                call_command('community_google_tts_connect',stdout=output)
            self.assertEqual(run.call_count,2)
            first=run.call_args_list[0]
            self.assertIn('--force',first.args[0]);self.assertIn('--update-adc',first.args[0])
            self.assertEqual(first.kwargs['env']['CLOUDSDK_CONFIG'],str(path.parent))
            self.assertNotIn('GOOGLE_APPLICATION_CREDENTIALS',first.kwargs['env'])
            self.assertNotIn('PYTHONHOME',first.kwargs['env']);self.assertNotIn('PYTHONPATH',first.kwargs['env'])
            self.assertNotIn('PRIVATE_TOKEN',output.getvalue());self.assertIn('Google TTS is connected',output.getvalue())
            connection.transport.close.assert_called_once()

    def test_interactive_login_does_not_replace_federation_or_continue_after_failed_login(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'application_default_credentials.json'
            path.write_text(json.dumps({'type':'external_account'}))
            with patch.object(connect,'windows_host',return_value=True), patch.object(google_tts,'credential_path',return_value=path), \
                 patch.object(connect,'find_gcloud',return_value='gcloud.cmd'), \
                 patch.object(connect.subprocess,'run',return_value=SimpleNamespace(returncode=1)) as run, \
                 patch.object(google_tts,'client') as client:
                with self.assertRaises(CommandError):call_command('community_google_tts_connect',stdout=io.StringIO())
                run.assert_not_called()
                path.write_text(json.dumps({'type':'authorized_user'}))
                with self.assertRaises(CommandError):call_command('community_google_tts_connect',stdout=io.StringIO())
                self.assertEqual(run.call_count,1);client.assert_not_called()
