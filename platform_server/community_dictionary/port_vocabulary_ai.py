"""Analyse a fixed accepted sentence with the same vocabulary rules as capture."""
import base64
import io
import json
from PIL import Image
from . import capture_ai
from .capture_vocabulary import WORD_INSTRUCTIONS, mwe_guidance
from .photo_ai import _openai_client

SCHEMA=capture_ai.obj({'words':capture_ai.SCHEMA['properties']['words']})
INSTRUCTIONS='''Extract learning vocabulary from this already accepted target-language sentence.
The sentence is authoritative. Do not translate source-language headwords or invent alternatives
to words actually used. The picture and commenting-language translation disambiguate the intended sense.
Return only words; do not rewrite the sentence or its translation. For example French
"Un bijou brillant en forme de lapin repose sur du tissu." contains repose -> reposer;
do not substitute être couché or se trouver merely because those could express a similar idea.
'''

def analyse(data,photo,*,model,api_key):
    content=[{'type':'input_text','text':json.dumps(data,ensure_ascii=False)}]
    if photo:
        with Image.open(io.BytesIO(photo)) as image:
            image.thumbnail((1024,1024));out=io.BytesIO();image.convert('RGB').save(out,'JPEG',quality=85)
        content.append({'type':'input_image','detail':'auto','image_url':'data:image/jpeg;base64,'+base64.b64encode(out.getvalue()).decode()})
    with _openai_client(api_key=api_key,timeout=45,max_retries=0) as client:
        return client.responses.create(model=model,instructions=INSTRUCTIONS+WORD_INSTRUCTIONS+mwe_guidance(data['target_language'])+'\nFor this request return only the sentence_vocabulary schema: words, without sentence fields.',
            input=[{'role':'user','content':content}],text={'format':{'type':'json_schema','name':'sentence_vocabulary','strict':True,'schema':SCHEMA}},
            reasoning={'effort':'low'},max_output_tokens=2600,store=False)

def parse(response,data):
    if getattr(response,'status',None)!='completed':
        raise ValueError('incomplete')
    value=json.loads(response.output_text)
    if not isinstance(value,dict) or set(value)!={'words'}:
        raise ValueError('schema')
    capture_ai.validate_words(value['words'],data['sentence'])
    eligible={word['id']:word for word in data.get('vocabulary',[])}
    for word in value['words']:
        match=eligible.get(word['existing_id'])
        if word['existing_id'] and (not match or (word['lemma'],word['meaning'])!=(match['lemma'],match['meaning'])):
            word['existing_id']=0
    return value
