import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
ROOT_DIR = BASE_DIR.parent
SRC_DIR = ROOT_DIR / "src"
USE_REAL_DJANGO_Q = os.environ.get("DJANGO_Q_USE_REAL", "").lower() in {
    "1",
    "true",
    "yes",
}
if str(SRC_DIR) not in sys.path:
    if USE_REAL_DJANGO_Q:
        sys.path.append(str(SRC_DIR))
    else:
        sys.path.insert(0, str(SRC_DIR))
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "dev-secret-key")
DEBUG = True
ALLOWED_HOSTS: list[str] = ["*"]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "projects",
    "django_q",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

# Use a database-backed session store so background threads can persist
# progress messages that are retrieved in subsequent requests. The default
# signed-cookie backend cannot be updated outside the request/response cycle.
SESSION_ENGINE = "django.contrib.sessions.backends.db"

ROOT_URLCONF = "platform_server.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "projects" / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "platform_server.wsgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

AUTH_PASSWORD_VALIDATORS = []

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "projects" / "static"]

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Auth redirects
LOGIN_REDIRECT_URL = "/"
LOGOUT_REDIRECT_URL = "/accounts/login/"

# Pipeline defaults for server integration
# Pipeline artifacts live under media/users/<user_id>/projects/project_<id>/runs/
# so each user’s runs are isolated while keeping relative links stable for HTML
# and audio assets.
PIPELINE_OUTPUT_ROOT = MEDIA_ROOT / "users"

Q_CLUSTER = {
    "name": "c-lara-2",
    "workers": 2,
    "timeout": 60 * 60,  # allow long compiles
    # Ensure retry exceeds timeout to satisfy django-q expectations and avoid
    # noisy warnings about misconfiguration.
    "retry": 60 * 90,
    "queue_limit": 50,
    "bulk": 10,
    "orm": "default",
}
