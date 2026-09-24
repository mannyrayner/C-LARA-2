"""Optional local browser rehearsal. Uses a disposable database and synthetic media.

Run with the repository's Python environment. Install Playwright separately,
then set COMMUNITY_PLAYWRIGHT_MODULE to its absolute module path if it is not
on Node's normal module search path. Chromium must be installed by Playwright,
or supplied through COMMUNITY_CHROMIUM_PATH. This never uses the server DB.
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
PROBE = Path(__file__).with_name('browser_workflow.cjs')


def main():
    output = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else ROOT / 'reports' / 'community-browser'
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='community-browser-') as temporary:
        scratch = Path(temporary)
        settings = scratch / 'community_rehearsal_settings.py'
        settings.write_text(
            'from platform_server.settings import *\n'
            f'DATABASES = {{"default": {{"ENGINE": "django.db.backends.sqlite3", "NAME": {str(scratch / "db.sqlite3")!r}}}}}\n'
            f'COMMUNITY_DICTIONARY_MEDIA_ROOT = Path({str(scratch / "private")!r})\n'
            f'MEDIA_ROOT = Path({str(scratch / "public")!r})\n'
            'PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]\n'
        )
        env = {**os.environ, 'PYTHONPATH': str(scratch), 'DJANGO_SETTINGS_MODULE': 'community_rehearsal_settings', 'COMMUNITY_BROWSER_OUTPUT': str(output)}
        subprocess.run([sys.executable, 'manage.py', 'migrate', '--noinput', '--settings', 'community_rehearsal_settings'], cwd=PLATFORM, env=env, check=True, stdout=subprocess.DEVNULL)
        seed = '''
import django
from pathlib import Path
import os
django.setup()
from django.contrib.auth import get_user_model
from community_dictionary.models import Dictionary, Membership, Partnership, Partner
from PIL import Image
User=get_user_model()
owner=User.objects.create_user(username='browser_owner',password='local-browser-trial-only')
member=User.objects.create_user(username='browser_member',password='local-browser-trial-only')
d=Dictionary.objects.create(name='Svenska tillsammans',language='Swedish',explanation_language='English',owner=owner)
Membership.objects.create(dictionary=d,user=member,accepted=True)
g=Partnership.objects.create(dictionary=d,name='Everyday Swedish',created_by=owner)
for u in (owner,member): Partner.objects.create(partnership=g,user=u,accepted=True)
Image.new('RGB',(2200,1800),'#427d67').save(Path(os.environ['COMMUNITY_BROWSER_OUTPUT'])/'browser-photo.png')
import math, struct, wave
with wave.open(str(Path(os.environ['COMMUNITY_BROWSER_OUTPUT'])/'microphone-tone.wav'), 'wb') as audio:
    audio.setparams((1, 2, 48000, 0, 'NONE', 'not compressed'))
    audio.writeframes(b''.join(struct.pack('<h', int(6000 * math.sin(2 * math.pi * 440 * i / 48000))) for i in range(48000)))
'''
        subprocess.run([sys.executable, '-c', seed], cwd=PLATFORM, env=env, check=True)
        # Refuse to attach the test to an unrelated service already using the port.
        with socket.socket() as probe:
            probe.bind(('127.0.0.1', 8765))
        with (output / 'server.log').open('w') as log:
            server = subprocess.Popen([sys.executable, 'manage.py', 'runserver', '127.0.0.1:8765', '--noreload', '--settings', 'community_rehearsal_settings'], cwd=PLATFORM, env=env, stdout=log, stderr=log)
            try:
                for _ in range(100):
                    if server.poll() is not None:
                        raise RuntimeError(f'Local server exited; see {output / "server.log"}')
                    try:
                        with socket.create_connection(('127.0.0.1', 8765), timeout=.1):
                            break
                    except OSError:
                        time.sleep(.1)
                else:
                    raise RuntimeError('Local server did not become ready')
                subprocess.run(['node', str(PROBE)], env=env, check=True)
            finally:
                server.terminate()
                server.wait(timeout=10)
        print(f'Browser screenshots and server log: {output}')


if __name__ == '__main__':
    main()
