"""Disposable public practice and owner guidance; dispatch/provider calls disabled."""
from public_browsing_browser_rehearsal import main

SEED = '''
dictionary.public_browsing_enabled=True
dictionary.discoverable=True
dictionary.sentence_capture_enabled=True
dictionary.save()
for word,meaning in [('katt','cat'),('hatt','hat'),('mat','food')]:
    e=entry(word,meaning,'word')
    for kind,data,mime,suffix in [('image',out.getvalue(),'image/jpeg','.jpg'),('audio',audio.getvalue(),'audio/wav','.wav')]:
        part=Contribution.objects.create(entry=e,author=user,kind=kind,**write_upload((data,mime,suffix),dictionary.pk,[]))
        accept(part,user)
'''
# Fake key is only a configuration fixture. No job can be dispatched, and any
# unexpected provider client creation fails immediately in this disposable app.
SERVER = '''
from django.conf import settings
settings.OPENAI_API_KEY='fixture-not-a-real-key'
import community_dictionary.port_tasks as tasks
import community_dictionary.photo_ai as ai
tasks.dispatch=lambda run_id: None
def no_provider(*args,**kwargs):
    raise AssertionError('Browser rehearsal must not contact a provider')
ai._openai_client=no_provider
'''

if __name__ == '__main__':
    main('practice_guidance_browser_workflow.cjs', SEED, SERVER)
