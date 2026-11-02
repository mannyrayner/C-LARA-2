"""Read configuration and optionally list Google voices; never synthesise speech."""
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from community_dictionary import google_tts
from community_dictionary.services import Conflict


class Command(BaseCommand):
    help = 'Check the configured Google word-audio credentials without generating audio or changing app data.'

    def add_arguments(self, parser):
        parser.add_argument('--username', required=True)
        parser.add_argument('--language', default='French')
        parser.add_argument('--voice')
        parser.add_argument('--contact-google', action='store_true', help='List voices to verify access; no synthesis charge.')

    def handle(self, *args, **options):
        try:
            user = get_user_model().objects.get(username=options['username'])
            google_tts.require_access(user)
            credentials = google_tts.credentials()
            self.stdout.write('Google project: ' + google_tts.project())
            self.stdout.write('Credential class: ' + type(credentials).__module__ + '.' + type(credentials).__name__)
            if options['contact_google']:
                google_tts.check_access(user, options['language'], selected_voice=options['voice'])
                self.stdout.write('Google voice access passed. No audio generated and no application data changed.')
            else:
                self.stdout.write('Local configuration passed. Google was not contacted. Add --contact-google to test access.')
        except get_user_model().DoesNotExist:
            raise CommandError('User not found.') from None
        except Conflict as exc:
            raise CommandError(str(exc)) from None
        except Exception as exc:
            raise CommandError('Google check failed ('+type(exc).__name__+'). No credentials are shown.') from None
