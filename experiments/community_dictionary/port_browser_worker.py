"""Test-only process injection; never import this from the production app."""
import io
import json
import math
import os
from pathlib import Path
import struct
import time
import threading
from types import SimpleNamespace
import wave
import django

django.setup()
from django.core.management import call_command
from community_dictionary import port_ai, tts


def event(data,event):
    with (Path(os.environ['COMMUNITY_BROWSER_OUTPUT'])/'queue-events.jsonl').open('a') as stream:
        stream.write(json.dumps({'word':data['word'],'event':event,'time':time.time(),'pid':os.getpid(),'thread':threading.get_ident()})+'\n')


def translate(data,photo,**kwargs):
    event(data,'start')
    time.sleep(1)
    result={'word':{'katt':'gatto','häst':'cavallo','tekanna':'teiera','tak':'tetto'}.get(data['word'],'parola '+data['word']),
            'meaning':data['meaning'],'category':data['category'],'feedback':'','outcome':'candidate','category_language':'commenting'}
    if data['word'] == 'tak':
        result['outcome'], result['feedback'] = 'unclear', 'Please check the picture; the word suggests a roof.'
    event(data,'end')
    return SimpleNamespace(status='completed',output_text=json.dumps(result),
        usage=SimpleNamespace(input_tokens=1200,output_tokens=100))


def speech(*args,**kwargs):
    out=io.BytesIO()
    with wave.open(out,'wb') as audio:
        audio.setparams((1,2,8000,0,'NONE','not compressed'))
        audio.writeframes(b''.join(struct.pack('<h',int(5000*math.sin(2*math.pi*440*i/8000))) for i in range(8000)))
    return (out.getvalue(),'audio/wav','.wav'),1.0


port_ai.translate=translate
tts.synthesize=speech
if __name__ == '__main__':
    call_command('qcluster')
