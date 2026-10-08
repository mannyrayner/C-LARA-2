"""Disposable sentence-port browser trial; all translation and TTS calls mocked.

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

SEED = '''
import django; django.setup()
from django.core.management import call_command
from django.contrib.auth import get_user_model
from community_dictionary.models import Dictionary, Entry, SentenceWord, ImageWordLink
from community_dictionary.services import add_contributions
from community_dictionary.tests.test_workflow import picture
from community_dictionary.storage import prepare_upload
call_command('migrate', verbosity=0)
owner=get_user_model().objects.create_user('owner', password='local-test-only')
d=Dictionary.objects.create(owner=owner,name='Swedish sentences',language='Swedish',explanation_language='English',sentence_capture_enabled=True)
s=Entry.objects.create(dictionary=d,created_by=owner,entry_type='sentence')
add_contributions(s,owner,{'word':'Katten ligger på soffan.','meaning':'The cat is lying on the sofa.',
    'prepared_photo':prepare_upload(picture(),'image')},[],publish=True)
s.refresh_from_db()
image=s.contributions.get(kind='image')
for lemma,meaning,surface in [('katt','cat','Katten'),('ligga','lie','ligger'),('på','on','på'),('soffa','sofa','soffan')]:
    word=Entry.objects.create(dictionary=d,created_by=owner)
    add_contributions(word,owner,{'word':lemma,'meaning':meaning},[],publish=True);word.refresh_from_db()
    SentenceWord.objects.create(sentence_text=s.current_text,word_entry=word,word_text=word.current_text,surface=surface)
    ImageWordLink.objects.create(image=image,word_entry=word,sentence_text=s.current_text,created_by=owner)
'''
SERVER = '''
import django; django.setup()
from django.core.management import call_command
from unittest.mock import patch
from community_dictionary import port_tasks
from community_dictionary.tests.test_porting import response,speech

def translate(data,photo,**kwargs):
    words={'katt':'chat','ligga':'être couché','på':'sur','soffa':'canapé'}
    if data.get('entry_type')=='sentence':
        surfaces={'katt':'Le chat','ligga':'est couché','på':'sur','soffa':'le canapé'}
        return response(word='Le chat est couché sur le canapé.',meaning=data['meaning'],category='',
            word_links=[{'source_entry_id':w['source_entry_id'],'surface':surfaces[w['word']]} for w in data['sentence_words']])
    return response(word=words[data['word']],meaning=data['meaning'],category='')
with patch('community_dictionary.port_ai.translate',side_effect=translate),patch('community_dictionary.tts.synthesize',side_effect=speech),patch('community_dictionary.port_tasks.send',side_effect=port_tasks.process_item):
    call_command('runserver','127.0.0.1:8771',use_reloader=False,insecure=True)
'''


def main():
    output = Path(sys.argv[1]).resolve() if len(sys.argv)>1 else ROOT/'reports'/'sentence-port-browser'
    output.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='sentence-port-browser-') as directory:
        temporary=Path(directory)
        (temporary/'sentence_rehearsal_settings.py').write_text(
            'from platform_server.settings import *\n'
            f'DATABASES={{"default":{{"ENGINE":"django.db.backends.sqlite3","NAME":{str(temporary/"db.sqlite3")!r}}}}}\n'
            f'COMMUNITY_DICTIONARY_MEDIA_ROOT=Path({str(temporary/"private")!r})\n'
            f'MEDIA_ROOT=Path({str(temporary/"public")!r})\n'
            'OPENAI_API_KEY="fixture-only"\nCREDITS_ENABLED=False\n'
            'ALLOWED_HOSTS=["127.0.0.1","localhost","testserver"]\n'
            'PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"]\n')
        env={**os.environ,'DJANGO_SETTINGS_MODULE':'sentence_rehearsal_settings',
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
                subprocess.run(['node',str(HERE/'sentence_port_browser_workflow.cjs')],env=env,check=True,timeout=120)
            finally:
                server.terminate();server.wait(timeout=10)
    print('Sentence-port browser trial passed; mocked providers and synchronous test dispatcher. '+str(output))

if __name__=='__main__': main()
