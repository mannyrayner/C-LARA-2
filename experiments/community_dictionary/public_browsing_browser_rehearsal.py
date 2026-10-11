"""Disposable visitor/owner rehearsal. No production data, email or AI calls."""
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
import io, math, struct, wave
from PIL import Image, ImageDraw
from django.core.management import call_command
from django.contrib.auth import get_user_model
from community_dictionary.models import Dictionary, Entry, Contribution, SentenceWord, ImageWordLink
from community_dictionary.services import accept
from community_dictionary.storage import write_upload
call_command('migrate',verbosity=0)
user=get_user_model().objects.create_user('owner','owner@example.org','browser-test-password-948')
dictionary=Dictionary.objects.create(name='Everyday Swedish', language='Swedish', explanation_language='English',owner=user)
Dictionary.objects.create(name='PRIVATE-DICTIONARY',language='Swedish',owner=user)
def entry(word,meaning,kind):
    e=Entry.objects.create(dictionary=dictionary,created_by=user,entry_type=kind)
    for field,value in [('word',word),('meaning',meaning),('category','Home')]:
        part=Contribution.objects.create(entry=e,author=user,kind='text',text_field=field,**{field:value})
        accept(part,user)
    e.refresh_from_db()
    return e
sentence=entry('En växt står på bordet.','A plant stands on the table.','sentence')
image=Image.new('RGB',(800,600),'#eadfc9');draw=ImageDraw.Draw(image)
draw.rectangle((0,440,800,600),fill='#996f4c');draw.polygon([(315,350),(485,350),(455,450),(345,450)],fill='#a5583d')
draw.line((400,360,400,130),fill='#31583b',width=12)
for box in [(275,185,402,265),(400,125,535,215),(300,80,405,175)]:draw.ellipse(box,fill='#547f49')
out=io.BytesIO();image.save(out,'JPEG')
picture=Contribution.objects.create(entry=sentence,author=user,kind='image',**write_upload((out.getvalue(),'image/jpeg','.jpg'),dictionary.pk,[]))
accept(picture,user)
audio=io.BytesIO()
with wave.open(audio,'wb') as wav:
    wav.setnchannels(1);wav.setsampwidth(2);wav.setframerate(8000)
    wav.writeframes(b''.join(struct.pack('<h',int(2000*math.sin(i*.2))) for i in range(8000)))
for word,meaning,surface in [('växt','plant','växt'),('stå på','stand on','står på'),('bord','table','bordet')]:
    e=entry(word,meaning,'word')
    sound=Contribution.objects.create(entry=e,author=user,kind='audio',**write_upload((audio.getvalue(),'audio/wav','.wav'),dictionary.pk,[]))
    accept(sound,user)
    SentenceWord.objects.create(sentence_text=sentence.current_text,word_entry=e,word_text=e.current_text,surface=surface)
    ImageWordLink.objects.create(image=picture,word_entry=e,created_by=user,sentence_text=sentence.current_text)
pending=Contribution.objects.create(entry=sentence,author=user,kind='text',word='PRIVATE-DRAFT')
Contribution.objects.create(entry=sentence,author=user,kind='note',status='accepted',body='PRIVATE-DISCUSSION')
'''


def main(workflow="public_browsing_browser_workflow.cjs", extra_seed=""):
    output = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else ROOT/'reports'/'public-browsing-browser'
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='public-browsing-') as directory:
        temporary = Path(directory)
        (temporary/'public_rehearsal_settings.py').write_text(
            'from platform_server.settings import *\n'
            f'DATABASES={{"default":{{"ENGINE":"django.db.backends.sqlite3","NAME":{str(temporary/"db.sqlite3")!r}}}}}\n'
            f'COMMUNITY_DICTIONARY_MEDIA_ROOT=Path({str(temporary/"private")!r})\n'
            'ALLOWED_HOSTS=["127.0.0.1","localhost"]\nCREDITS_ENABLED=False\n'
            'PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"]\n')
        env = {**os.environ, 'DJANGO_SETTINGS_MODULE': 'public_rehearsal_settings',
               'PYTHONPATH': str(temporary)+os.pathsep+os.environ.get('PYTHONPATH', ''),
               'COMMUNITY_BROWSER_OUTPUT': str(output)}
        subprocess.run([sys.executable, '-c', SEED + extra_seed], cwd=PLATFORM, env=env, check=True)
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', 8773))
        with (output/'server.log').open('w') as log:
            server = subprocess.Popen([sys.executable, '-c',
                'import django; django.setup(); from django.core.management import call_command; '
                'call_command("runserver","127.0.0.1:8773",use_reloader=False,insecure=True)'],
                cwd=PLATFORM, env=env, stdout=log, stderr=log)
            try:
                for _ in range(100):
                    if server.poll() is not None:
                        raise RuntimeError('Server stopped; see server.log')
                    try:
                        with socket.create_connection(('127.0.0.1', 8773), timeout=.1):
                            break
                    except OSError:
                        time.sleep(.1)
                else:
                    raise RuntimeError('Server did not start')
                subprocess.run(['node', str(HERE/workflow)],
                               env=env, check=True, timeout=120)
            finally:
                server.terminate()
                server.wait(timeout=10)
    print('Visitor and owner browser rehearsal passed. '+str(output))


if __name__ == '__main__':
    main()
