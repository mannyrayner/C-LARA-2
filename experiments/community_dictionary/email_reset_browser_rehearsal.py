"""Disposable recovery rehearsal: real background dispatcher, captured mail, no SMTP."""
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
call_command('migrate',verbosity=0)
for i in range(6):
    get_user_model().objects.create_user('learner'+str(i),'learner'+str(i)+'@example.org','old-test-password-948')
'''
SERVER = '''
import django; django.setup()
import json, os
from pathlib import Path
from unittest.mock import patch
from django.core.management import call_command

def capture(message, **kwargs):
    Path(os.environ['COMMUNITY_BROWSER_OUTPUT'],message.to[0]+'.json').write_text(json.dumps({'body':message.body,'subject':message.subject}))
    return 1
with patch('projects.email_reset.EmailMultiAlternatives.send',capture):
    call_command('runserver','127.0.0.1:8772',use_reloader=False,insecure=True)
'''

def main():
    output=Path(sys.argv[1]).resolve() if len(sys.argv)>1 else ROOT/'reports'/'email-reset-browser'
    output.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='email-reset-browser-') as directory:
        temporary=Path(directory)
        (temporary/'email_rehearsal_settings.py').write_text(
            'from platform_server.settings import *\n'
            f'DATABASES={{"default":{{"ENGINE":"django.db.backends.sqlite3","NAME":{str(temporary/"db.sqlite3")!r}}}}}\n'
            'PASSWORD_RESET_EMAIL_ENABLED=True\nPUBLIC_BASE_URL="http://127.0.0.1:8772"\n'
            'DEFAULT_FROM_EMAIL="test@example.org"\nEMAIL_BACKEND="django.core.mail.backends.console.EmailBackend"\n'
            'ALLOWED_HOSTS=["127.0.0.1","localhost"]\nCREDITS_ENABLED=False\n'
            'PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"]\n')
        env={**os.environ,'DJANGO_SETTINGS_MODULE':'email_rehearsal_settings',
             'PYTHONPATH':str(temporary)+os.pathsep+os.environ.get('PYTHONPATH',''),
             'COMMUNITY_BROWSER_OUTPUT':str(output)}
        subprocess.run([sys.executable,'-c',SEED],cwd=PLATFORM,env=env,check=True)
        with socket.socket() as sock: sock.bind(('127.0.0.1',8772))
        with (output/'server.log').open('w') as log:
            server=subprocess.Popen([sys.executable,'-c',SERVER],cwd=PLATFORM,env=env,stdout=log,stderr=log)
            try:
                for _ in range(100):
                    if server.poll() is not None: raise RuntimeError('Server stopped; see server.log')
                    try:
                        with socket.create_connection(('127.0.0.1',8772),timeout=.1): break
                    except OSError: time.sleep(.1)
                else: raise RuntimeError('Server did not start')
                subprocess.run(['node',str(HERE/'email_reset_browser_workflow.cjs')],env=env,check=True,timeout=120)
            finally:
                server.terminate();server.wait(timeout=10)
    print('Email reset browser rehearsal passed. No SMTP used. '+str(output))

if __name__=='__main__': main()
