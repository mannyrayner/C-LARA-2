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


def main(workflow=PROBE, image_generation=False, practice=False, porting=False):
    output = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else ROOT / 'reports' / 'community-browser'
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='community-browser-') as temporary:
        scratch = Path(temporary)
        settings = scratch / 'community_rehearsal_settings.py'
        settings.write_text(
            'from platform_server.settings import *\n'
            'DEBUG = True\n'
            f'DATABASES = {{"default": {{"ENGINE": "django.db.backends.sqlite3", "NAME": {str(scratch / "db.sqlite3")!r}}}}}\n'
            f'COMMUNITY_DICTIONARY_MEDIA_ROOT = Path({str(scratch / "private")!r})\n'
            f'MEDIA_ROOT = Path({str(scratch / "public")!r})\n'
            'PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]\n'
        )
        env = {**os.environ, 'PYTHONPATH': str(scratch) + os.pathsep + os.environ.get('PYTHONPATH', ''), 'DJANGO_SETTINGS_MODULE': 'community_rehearsal_settings', 'COMMUNITY_BROWSER_OUTPUT': str(output)}
        real_port_queue = porting and os.environ.get('COMMUNITY_PORT_BROWSER_QUEUE','real') == 'real'
        if porting:
            env['DJANGO_Q_USE_REAL'] = '1' if real_port_queue else '0'
            (output / 'queue-events.jsonl').unlink(missing_ok=True)
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
        if image_generation:
            with settings.open('a') as stream:
                stream.write('OPENAI_API_KEY = "local-fixture-not-real"\nCREDITS_ENABLED = False\n')
            seed += '''
from community_dictionary.models import Entry
Entry.objects.create(dictionary=d, created_by=owner, word='tekanna', meaning='teapot')
'''
        if practice or porting:
            seed += '''
from community_dictionary.models import Entry
from community_dictionary.services import add_contributions
from PIL import ImageDraw
import io
words=[('katt','cat'),('tak','roof'),('anka','duck'),('kanin','rabbit'),('häst','horse'),('tekanna','teapot'),('fartölva','laptop'),('en häst','a horse')]
for index,(word,meaning) in enumerate(words):
    entry=Entry.objects.create(dictionary=d,created_by=owner)
    picture=Image.new('RGB',(480,360),['#eee4cc','#d5e7dd','#e6dcf1','#dce9f5'][index%4])
    draw=ImageDraw.Draw(picture)
    draw.ellipse((140,80,340,285),fill='#669985',outline='#23473f',width=4)
    draw.ellipse((175,145,195,165),fill='#23473f')
    draw.ellipse((270,145,290,165),fill='#23473f')
    out=io.BytesIO();picture.save(out,'PNG')
    add_contributions(entry,owner,{'word':word,'meaning':meaning,'category':'Home' if index%2 else 'Outside',
        'prepared_photo':(out.getvalue(),'image/png','.png'),
        'prepared_audio':((Path(os.environ['COMMUNITY_BROWSER_OUTPUT'])/'microphone-tone.wav').read_bytes(),'audio/wav','.wav')},[],publish=True)
'''
        if porting:
            with settings.open('a') as stream:
                stream.write('OPENAI_API_KEY = \"local-fixture-not-real\"\nCREDITS_ENABLED = True\nQ_CLUSTER = {**Q_CLUSTER, \"workers\": 2, \"poll\": .2}\nCOMMUNITY_DICTIONARY_PORT_WINDOW = 2\n')
            seed += '\nfrom projects.models import CreditAccount\nCreditAccount.objects.create(user=owner,balance_usd=1)\n'
        subprocess.run([sys.executable, '-c', seed], cwd=PLATFORM, env=env, check=True)
        # Refuse to attach the test to an unrelated service already using the port.
        with socket.socket() as probe:
            probe.bind(('127.0.0.1', 8765))
        with (output / 'server.log').open('w') as log:
            command = [sys.executable, 'manage.py', 'runserver', '127.0.0.1:8765', '--noreload', '--settings', 'community_rehearsal_settings']
            if image_generation:
                # Test-only process injection; no production backend switch or paid call.
                command = [sys.executable, '-c', '''
import django, io, time
django.setup()
from PIL import Image, ImageDraw
from django.core.management import call_command
from community_dictionary import image_generation as images
def fixture(study, key):
    time.sleep(.4)
    picture=Image.new('RGB',(640,640),'#f5f4ee')
    draw=ImageDraw.Draw(picture)
    draw.ellipse((130,240,450,500),fill='#67958a')
    draw.polygon([(425,315),(575,235),(480,415)],fill='#67958a')
    draw.ellipse((75,295,205,450),outline='#67958a',width=26)
    draw.rectangle((245,215,335,240),fill='#365e56')
    draw.text((165,555),'SIMULATED PROVIDER RESPONSE',fill='#365e56')
    out=io.BytesIO();picture.save(out,'JPEG')
    return (out.getvalue(),'image/jpeg','.jpg'), {'prompt_tokens':100,'completion_tokens':2000,'total_tokens':2100}, ''
images.generate=fixture
call_command('runserver','127.0.0.1:8765',use_reloader=False)
''']
            worker = None
            if real_port_queue:
                worker = subprocess.Popen([sys.executable, str(Path(__file__).with_name('port_browser_worker.py'))], cwd=PLATFORM, env={**env, 'PYTHONPATH':str(PLATFORM)+os.pathsep+env['PYTHONPATH']}, stdout=log, stderr=log)
            if porting and not real_port_queue:
                command = [sys.executable, '-c', 'import django,runpy; django.setup(); runpy.run_path('+repr(str(Path(__file__).with_name('port_browser_worker.py')))+'); from django.core.management import call_command; call_command(\"runserver\",\"127.0.0.1:8765\",use_reloader=False)']
            server = subprocess.Popen(command, cwd=PLATFORM, env=env, stdout=log, stderr=log)
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
                subprocess.run(['node', str(workflow)], env=env, check=True)
            finally:
                server.terminate()
                server.wait(timeout=10)
                if worker:
                    worker.terminate()
                    worker.wait(timeout=20)
        print(f'Browser screenshots and server log: {output}')


if __name__ == '__main__':
    main()
