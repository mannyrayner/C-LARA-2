"""Isolated pilot settings. This module is selected only by staging services."""
from .settings import *
from django.core.exceptions import ImproperlyConfigured

if os.environ.get('CLARA_STAGING_MODE') != '1':
    raise ImproperlyConfigured('Explicit staging mode is required.')
if (DATABASES['default']['ENGINE'] != 'django.db.backends.postgresql' or
        DATABASES['default']['HOST'] != '127.0.0.1' or
        DATABASES['default']['NAME'] != 'clara_staging' or
        DATABASES['default']['USER'] != 'clara_staging'):
    raise ImproperlyConfigured('Staging requires its isolated local database.')
if SECRET_KEY == 'dev-secret-key' or not DATABASES['default']['PASSWORD']:
    raise ImproperlyConfigured('Independent staging credentials are required.')
ALLOWED_HOSTS = [os.environ['CLARA_STAGING_HOSTNAME'], '127.0.0.1', 'localhost']
CSRF_TRUSTED_ORIGINS = ['https://' + os.environ['CLARA_STAGING_HOSTNAME']]
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
PASSWORD_RESET_EMAIL_ENABLED = False
EMAIL_BACKEND = 'django.core.mail.backends.filebased.EmailBackend'
EMAIL_FILE_PATH = '/var/lib/clara-staging-mail'
MEDIA_ROOT = Path('/var/lib/clara-staging-media')
COMMUNITY_DICTIONARY_MEDIA_ROOT = Path('/var/lib/clara-staging-private/community_dictionary')
PIPELINE_OUTPUT_ROOT = MEDIA_ROOT / 'users'
USE_REAL_DJANGO_Q = False
Q_CLUSTER = {**Q_CLUSTER, 'workers': 1, 'queue_limit': 10}
ROOT_URLCONF = 'platform_server.staging_urls'
