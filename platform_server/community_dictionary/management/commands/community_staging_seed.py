"""Prepare fixed synthetic browser fixtures in the isolated staging database."""
import hashlib
import hmac
import io
import json
import math
import os
from pathlib import Path
import struct
import wave

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.urls import reverse
from PIL import Image

from community_dictionary.models import Contribution, Dictionary, Entry
from community_dictionary.storage import write_upload


def seed(secret):
    passwords = {name: hmac.new(secret['seed'].encode(), name.encode(), hashlib.sha256).hexdigest()
                 for name in ('owner_password', 'other_password')}
    User = get_user_model()
    with transaction.atomic():
        users = []
        for username, name in [('staging-owner','owner_password'),('staging-outsider','other_password')]:
            user, created = User.objects.get_or_create(username=username)
            if not created and (user.is_superuser or user.is_staff):
                raise CommandError('Unexpected fixture user privileges; inspect before proceeding.')
            user.set_password(passwords[name]); user.save()
            users.append(user)
        dictionary, _ = Dictionary.objects.get_or_create(owner=users[0], name='Staging private fixture',
            defaults={'language':'English','explanation_language':'English','photo_ai_enabled':False,
                      'tts_enabled':False,'image_generation_enabled':False})
        if dictionary.public_browsing_enabled or dictionary.discoverable:
            raise CommandError('Fixture dictionary unexpectedly shared; inspect before proceeding.')
        entry = dictionary.entries.filter(word='Synthetic staging object', archived=False).first()
        if entry is None:
            entry = Entry.objects.create(dictionary=dictionary, created_by=users[0],
                word='Synthetic staging object',meaning='Deployment test fixture',category='Staging')
            text = Contribution.objects.create(entry=entry, author=users[0], kind='text', status='accepted',
                word=entry.word, meaning=entry.meaning, category=entry.category, text_field='word')
            picture = io.BytesIO(); Image.new('RGB',(32,24),'green').save(picture,'JPEG')
            audio = io.BytesIO()
            with wave.open(audio,'wb') as stream:
                stream.setnchannels(1); stream.setsampwidth(2); stream.setframerate(8000)
                stream.writeframes(b''.join(struct.pack('<h',int(1000*math.sin(i*2*math.pi*440/8000)))
                                           for i in range(1600)))
            created_paths = []
            image = Contribution.objects.create(entry=entry,author=users[0],kind='image',status='accepted',
                label='Synthetic fixture image',provenance={'method':'staging_fixture'},
                **write_upload((picture.getvalue(),'image/jpeg','.jpg'),dictionary.pk,created_paths))
            Contribution.objects.create(entry=entry,author=users[0],kind='audio',status='accepted',
                label='Synthetic test tone (not speech)',provenance={'method':'staging_fixture'},
                **write_upload((audio.getvalue(),'audio/wav','.wav'),dictionary.pk,created_paths))
            entry.current_text, entry.selected_image = text,image
            entry.text_version = 1; entry.save()
        images = entry.contributions.filter(kind='image',status='accepted')
        audio = entry.contributions.filter(kind='audio',status='accepted')
        if not images.exists() or not audio.exists():
            raise CommandError('Incomplete existing fixture; inspect before repair.')
        return {'schema':1,'word':entry.word,
            'dictionary_url':reverse('community_dictionary:dictionary',args=[dictionary.pk]),
            'entry_url':reverse('community_dictionary:entry',args=[dictionary.pk,entry.pk]),
            'image_url':reverse('community_dictionary:media',args=[dictionary.pk,images.first().pk]),
            'audio_url':reverse('community_dictionary:media',args=[dictionary.pk,audio.first().pk])}


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument('--secret-file', required=True)
        parser.add_argument('--output', required=True)

    def handle(self,*args,**options):
        database = settings.DATABASES['default']
        if (os.environ.get('CLARA_STAGING_MODE') != '1' or
                database['ENGINE'] != 'django.db.backends.postgresql' or
                database['HOST'] != '127.0.0.1' or database['NAME'] != 'clara_staging'):
            raise CommandError('This command is restricted to the isolated staging database.')
        secret = json.loads(Path(options['secret_file']).read_text())
        if not isinstance(secret.get('seed'),str) or len(secret['seed']) < 24:
            raise CommandError('Staging seed required.')
        data = seed(secret)
        Path(options['output']).write_text(json.dumps(data,indent=2)+'\n')
        self.stdout.write('Prepared synthetic fixture; no provider calls.')
