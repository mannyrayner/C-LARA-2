import tempfile
from pathlib import Path
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase,override_settings

from community_dictionary.management.commands.community_staging_seed import seed
from community_dictionary.models import Contribution,Dictionary,Entry


class StagingFixtureTests(TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        override=override_settings(COMMUNITY_DICTIONARY_MEDIA_ROOT=Path(self.temp.name)/'private',
                                   MEDIA_ROOT=Path(self.temp.name)/'public')
        override.enable();self.addCleanup(override.disable)

    def test_repeatable_private_fixture_and_real_access_boundaries(self):
        with patch('projects.views._build_ai_client',side_effect=AssertionError('No AI')):
            fixture=seed({'seed':'x'*40})
            self.assertEqual(fixture,seed({'seed':'x'*40}))
        self.assertEqual(Dictionary.objects.count(),1);self.assertEqual(Entry.objects.count(),1)
        self.assertEqual(Contribution.objects.count(),3)
        owner=get_user_model().objects.get(username='staging-owner')
        other=get_user_model().objects.get(username='staging-outsider')
        self.client.force_login(owner)
        for key in ('entry_url','image_url','audio_url'):
            self.assertEqual(self.client.get(fixture[key]).status_code,200)
        self.client.force_login(other)
        for key in ('entry_url','image_url','audio_url'):
            self.assertIn(self.client.get(fixture[key]).status_code,(403,404))
        dictionary=Dictionary.objects.get()
        self.assertFalse(dictionary.photo_ai_enabled or dictionary.tts_enabled or
                         dictionary.image_generation_enabled or dictionary.public_browsing_enabled)

    def test_command_refuses_production_or_sqlite_before_reading_credentials(self):
        with self.assertRaises(CommandError):
            call_command('community_staging_seed',secret_file='/missing',output='/missing')
