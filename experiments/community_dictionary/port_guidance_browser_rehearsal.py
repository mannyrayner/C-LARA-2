"""Linked-dictionary suggestions on disposable data, with no provider requests."""
from public_browsing_browser_rehearsal import main
from practice_guidance_browser_rehearsal import SERVER

SEED = '''
import uuid
from unittest.mock import patch
from django.conf import settings
from community_dictionary import porting, port_tasks, port_vocabulary as vocab
from community_dictionary.models import VocabularyState
from community_dictionary.services import add_contributions
from community_dictionary.tests.test_porting import response, speech
settings.OPENAI_API_KEY='fixture-only'
dictionary.sentence_capture_enabled=True
dictionary.save()
with patch('community_dictionary.port_tasks.send'), patch('community_dictionary.port_ai.translate',return_value=response(word='Une plante repose sur la table.',meaning='A plant stands on the table.',category='Home')), patch('community_dictionary.tts.synthesize',side_effect=speech):
    run=porting.quote(user,dictionary,dict(name='French version',language='French',explanation_language='English',voice='marin'),uuid.uuid4())
    assert run.items.count()==1
    run=porting.approve(user,run.pk)
    item=run.items.get()
    port_tasks.process_item(item.pk)
    item.refresh_from_db()
    translated=porting.save_item(user,item.pk,item.result)
VocabularyState.objects.create(sentence=translated,snapshot=vocab.sentence_snapshot(translated),recipe=vocab.VERSION,words=[],accepted_by=user)
for n in range(6):
    extra=entry(f'En ny växt står på bordet {n+1}.','A new plant stands on the table.','sentence')
    add_contributions(extra,user,{'prepared_photo':(out.getvalue(),'image/jpeg','.jpg')},[],publish=True)
'''

if __name__ == '__main__':
    main('port_guidance_browser_workflow.cjs', SEED, SERVER)
