"""Disposable browser rehearsal with a mocked provider; never calls OpenAI.

Requires Playwright and Chromium. See browser_rehearsal.py for dependency variables.
"""
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[2]
PLATFORM = ROOT / 'platform_server'


def main():
    output = Path(sys.argv[1]).resolve()
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='community-photo-') as temporary:
        scratch = Path(temporary)
        (scratch/'photo_settings.py').write_text(
            'from platform_server.settings import *\nDEBUG=True\n'
            f'DATABASES={{"default":{{"ENGINE":"django.db.backends.sqlite3","NAME":{str(scratch/"db.sqlite3")!r}}}}}\n'
            f'COMMUNITY_DICTIONARY_MEDIA_ROOT=Path({str(scratch/"private")!r})\n'
            f'MEDIA_ROOT=Path({str(scratch/"public")!r})\n'
            'PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"]\n'
            'OPENAI_API_KEY="mock-only"\nCREDITS_ENABLED=False\n')
        env = {**os.environ, 'PYTHONPATH': str(scratch)+os.pathsep+os.environ.get('PYTHONPATH', ''),
               'DJANGO_SETTINGS_MODULE': 'photo_settings', 'COMMUNITY_BROWSER_OUTPUT': str(output)}
        subprocess.run([sys.executable, 'manage.py', 'migrate', '--noinput', '--settings', 'photo_settings'], cwd=PLATFORM, env=env, check=True, stdout=subprocess.DEVNULL)
        seed = '''
import django, os
from pathlib import Path
django.setup()
from django.contrib.auth import get_user_model
from community_dictionary.models import Dictionary
from PIL import Image
owner=get_user_model().objects.create_user(username='photo_owner',password='local-photo-test')
Dictionary.objects.create(owner=owner,name='Italian around us',language='Italian',explanation_language='English',photo_ai_enabled=True,tts_enabled=True)
Image.new('RGB',(2200,1800),'#427d67').save(Path(os.environ['COMMUNITY_BROWSER_OUTPUT'])/'fixture.png')
'''
        subprocess.run([sys.executable, '-c', seed], cwd=PLATFORM, env=env, check=True)
        server_code = '''
import django
django.setup()
from unittest.mock import patch
from community_dictionary.tests.test_photo_learning import response
from community_dictionary.tests.test_entry_media import speech_fixture
from django.core.management import call_command
with patch('community_dictionary.photo_ai.analyse', return_value=response()), patch('community_dictionary.tts.synthesize', return_value=speech_fixture()):
    call_command('runserver','127.0.0.1:8766',use_reloader=False)
'''
        with socket.socket() as probe: probe.bind(('127.0.0.1', 8766))
        with (output/'server.log').open('w') as log:
            server = subprocess.Popen([sys.executable, '-c', server_code], cwd=PLATFORM, env=env, stdout=log, stderr=log)
            try:
                for _ in range(100):
                    if server.poll() is not None: raise RuntimeError('Server exited; inspect server.log')
                    try:
                        with socket.create_connection(('127.0.0.1', 8766), timeout=.1): break
                    except OSError: time.sleep(.1)
                else: raise RuntimeError('Server did not start')
                subprocess.run(['node', str(Path(__file__).with_name('photo_browser_workflow.cjs'))], env=env, check=True)
            finally:
                server.terminate(); server.wait(timeout=10)
        print(f'Photo browser evidence: {output}')


if __name__ == '__main__': main()
