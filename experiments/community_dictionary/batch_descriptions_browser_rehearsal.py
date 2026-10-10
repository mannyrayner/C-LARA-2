"""Disposable same-dictionary batch browser trial; all translation and TTS calls mocked.

Use the application Python environment, plus Playwright/Chromium as described in
browser_rehearsal.py. Optional first argument: screenshot output directory.
"""
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
PLATFORM = ROOT / 'platform_server'

SEED = r'''
import django; django.setup()
from django.core.management import call_command
from django.contrib.auth import get_user_model
from community_dictionary.models import Dictionary, Entry
from community_dictionary.services import add_contributions
from community_dictionary.tests.test_workflow import picture
from community_dictionary.storage import prepare_upload
call_command('migrate', verbosity=0)
owner=get_user_model().objects.create_user('owner', password='local-test-only')
d=Dictionary.objects.create(owner=owner,name='Swedish pictures',language='Swedish',explanation_language='English',sentence_capture_enabled=True)
for pending, hint in [(True, ''), (False, 'cat')]:
    entry=Entry.objects.create(dictionary=d,created_by=owner)
    add_contributions(entry,owner,{'meaning':hint,'prepared_photo':prepare_upload(picture(),'image')},[],publish=not pending)
'''
SERVER = r'''
import django; django.setup()
from django.core.management import call_command
from unittest.mock import patch
from community_dictionary import port_tasks, port_vocabulary_tasks
from community_dictionary.tests.test_batch_descriptions import description,WORDS
from community_dictionary.tests.test_porting import speech

def vocabulary(data,photo,**kwargs):
    import json
    from types import SimpleNamespace
    return SimpleNamespace(status='completed',usage=SimpleNamespace(input_tokens=1000,output_tokens=150),output_text=json.dumps({'words':WORDS}))
with patch('community_dictionary.batch_descriptions.interpret',return_value=description()),patch('community_dictionary.port_vocabulary_ai.analyse',side_effect=vocabulary),patch('community_dictionary.tts.synthesize',side_effect=speech),patch('community_dictionary.port_tasks.send',side_effect=port_tasks.process_item),patch('community_dictionary.port_vocabulary_tasks.send_speech',side_effect=port_vocabulary_tasks.speak):
    call_command('runserver','127.0.0.1:8771',use_reloader=False,insecure=True)
'''


def main():
    output = Path(sys.argv[1]).resolve() if len(sys.argv)>1 else ROOT/'reports'/'batch-descriptions-browser'
    output.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='batch-descriptions-browser-') as directory:
        temporary=Path(directory)
        (temporary/'batch_rehearsal_settings.py').write_text(
            'from platform_server.settings import *\n'
            f'DATABASES={{"default":{{"ENGINE":"django.db.backends.sqlite3","NAME":{str(temporary/"db.sqlite3")!r}}}}}\n'
            f'COMMUNITY_DICTIONARY_MEDIA_ROOT=Path({str(temporary/"private")!r})\n'
            f'MEDIA_ROOT=Path({str(temporary/"public")!r})\n'
            'OPENAI_API_KEY="fixture-only"\nCREDITS_ENABLED=False\n'
            'ALLOWED_HOSTS=["127.0.0.1","localhost","testserver"]\n'
            'PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"]\n')
        env={**os.environ,'DJANGO_SETTINGS_MODULE':'batch_rehearsal_settings',
             'PYTHONPATH':str(temporary)+os.pathsep+os.environ.get('PYTHONPATH',''),
             'COMMUNITY_BROWSER_OUTPUT':str(output)}
        subprocess.run([sys.executable,'-c',SEED],cwd=PLATFORM,env=env,check=True)
        with socket.socket() as sock: sock.bind(('127.0.0.1',8771))
        with (output/'server.log').open('w') as log:
            server=subprocess.Popen([sys.executable,'-c',SERVER],cwd=PLATFORM,env=env,stdout=log,stderr=log)
            try:
                for attempt in range(100):
                    if server.poll() is not None: raise RuntimeError('Server stopped; see server.log')
                    try:
                        with socket.create_connection(('127.0.0.1',8771),timeout=.1): break
                    except OSError: time.sleep(.1)
                else: raise RuntimeError('Server did not start')
                subprocess.run(['node',str(HERE/'batch_descriptions_browser_workflow.cjs')],env=env,check=True,timeout=120)
            finally:
                server.terminate();server.wait(timeout=10)
    print('Batch-descriptions browser trial passed; mocked providers and synchronous test dispatcher. '+str(output))

if __name__=='__main__': main()
