"""Interactive Windows-only login helper; never invoked by an HTTP request."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

from django.core.management.base import BaseCommand, CommandError
from community_dictionary import google_tts


def windows_host():
    return os.name == 'nt'


def find_gcloud():
    found = shutil.which('gcloud.cmd')
    if found:
        return found
    for root in (os.environ.get('LOCALAPPDATA'), os.environ.get('ProgramFiles(x86)'), os.environ.get('ProgramFiles')):
        if not root:
            continue
        for prefix in ('', 'Programs'):
            candidate = Path(root) / prefix / 'Google' / 'Cloud SDK' / 'google-cloud-sdk' / 'bin' / 'gcloud.cmd'
            if candidate.is_file():
                return str(candidate)
    raise CommandError('Google Cloud CLI was not found. Install it, then open this launcher again.')


class Command(BaseCommand):
    help = 'Connect Google TTS on this Windows laptop using one browser sign-in, then verify access. No audio generation.'

    def handle(self, *args, **options):
        if not windows_host():
            raise CommandError('This interactive helper is for the Windows laptop. AWS uses its existing federation configuration.')
        destination = google_tts.credential_path().resolve()
        if destination.name != 'application_default_credentials.json':
            raise CommandError('This host uses a custom credential file. Ask the administrator to check its configuration; it was not changed.')
        if destination.exists():
            try:
                info = json.loads(destination.read_text(encoding='utf-8'))
            except (OSError, ValueError):
                raise CommandError('The existing credential file could not be read; it was not changed.') from None
            if not isinstance(info, dict) or info.get('type') != 'authorized_user':
                raise CommandError('This is not a laptop user-credential file; it was not changed.')
        executable = find_gcloud()
        env = dict(os.environ)
        env['CLOUDSDK_CONFIG'] = str(destination.parent)
        env['CLOUDSDK_PYTHON'] = sys._base_executable
        for key in ('PYTHONHOME', 'PYTHONPATH', 'GOOGLE_APPLICATION_CREDENTIALS'):
            env.pop(key, None)
        self.stdout.write('Connect Google TTS: select your authorised Google account in the browser.')
        self.stdout.write('Credential location: ' + str(destination))
        self.stdout.write('Google project: ' + google_tts.project())
        # --force avoids quietly reusing a cached login; --update-adc writes
        # the credentials the application actually reads. No credentials pass
        # through this process output capture or into project files.
        commands = [
            ['auth', 'login', '--force', '--update-adc', '--project=' + google_tts.project(),
             '--billing-project=' + google_tts.project()],
            ['auth', 'application-default', 'set-quota-project', google_tts.project()],
        ]
        for arguments in commands:
            result = subprocess.run([executable, *arguments], env=env)
            if result.returncode:
                raise CommandError('Google sign-in/setup did not finish. No audio was generated. You can reopen this launcher to retry.')
        connection = None
        try:
            connection = google_tts.client()
            response = connection.list_voices(request={'language_code':'en-GB'}, retry=None, timeout=30)
            names = {v.name for v in response.voices}
            if not {'en-GB-Wavenet-F', 'en-GB-Neural2-F'} <= names:
                raise google_tts.GoogleAccessError('voices', 'voice availability')
        except google_tts.GoogleAccessError as exc:
            raise CommandError(str(exc) + ' Stage: ' + exc.stage + '.') from None
        except Exception as exc:
            error = google_tts.access_error(exc, 'voice listing')
            raise CommandError(str(error) + ' Stage: ' + error.stage + '.') from None
        finally:
            if connection is not None:
                connection.transport.close()
        self.stdout.write(self.style.SUCCESS('Google TTS is connected. Return to the evaluation page and click Check Google connection. No audio was generated.'))
