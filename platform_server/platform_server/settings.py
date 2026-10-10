import os
import json
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
DEBUG = False
ALLOWED_HOSTS: list[str] = ["*"]

# Keep DEBUG off while making request tracebacks available to systemd's journal.
# Django's default production request handler emails admins, which may not be
# configured. Stream only server errors; do not expose debug pages to visitors.
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {
        "request_errors": {
            "class": "logging.StreamHandler",
            "level": "ERROR",
            "stream": "ext://sys.stderr",
        },
    },
    "loggers": {
        "django.request": {
            "handlers": ["request_errors"],
            "level": "ERROR",
            "propagate": False,
        },
    },
}

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "projects",
    "community_dictionary.apps.CommunityDictionaryConfig",
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
    "community_dictionary.middleware.PrivatePagesMiddleware",
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
                "projects.context_processors.credit_balance",
                "projects.email_reset.recovery_context",
            ],
        },
    },
]

WSGI_APPLICATION = "platform_server.wsgi.application"

USE_POSTGRES = os.environ.get("POSTGRES_HOST") or os.environ.get("DJANGO_DB_ENGINE", "").lower() in {
    "postgres",
    "postgresql",
}

if USE_POSTGRES:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": os.environ.get("POSTGRES_DB", "clara2"),
            "USER": os.environ.get("POSTGRES_USER", "postgres"),
            "PASSWORD": os.environ.get("POSTGRES_PASSWORD", ""),
            "HOST": os.environ.get("POSTGRES_HOST", ""),
            "PORT": os.environ.get("POSTGRES_PORT", "5432"),
        }
    }
else:
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

# Human-contributed dictionary media must not be served by the public /media/ alias.
COMMUNITY_DICTIONARY_MEDIA_ROOT = Path(os.environ.get(
    "CLARA_COMMUNITY_MEDIA_ROOT", str(BASE_DIR / "private_uploads" / "community_dictionary")
))

# Explicit, bounded image previews. Per-dictionary permission defaults off.
COMMUNITY_DICTIONARY_IMAGE_MODEL = os.environ.get("CLARA_COMMUNITY_IMAGE_MODEL", "gpt-image-2.5-sunburst")
COMMUNITY_DICTIONARY_IMAGE_DAILY_LIMIT = int(os.environ.get("CLARA_COMMUNITY_IMAGE_DAILY_LIMIT", "20"))
COMMUNITY_DICTIONARY_IMAGE_ALLOWANCE_USD = os.environ.get("CLARA_COMMUNITY_IMAGE_ALLOWANCE_USD", "0.50")

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Auth redirects
LOGIN_REDIRECT_URL = "/"
LOGOUT_REDIRECT_URL = "/accounts/login/"

# Outgoing recovery mail. Disabled until the operator configures and tests it.
PASSWORD_RESET_EMAIL_ENABLED = os.environ.get("CLARA_PASSWORD_RESET_ENABLED", "").lower() in {"1", "true", "yes"}
PUBLIC_BASE_URL = os.environ.get("CLARA_PUBLIC_BASE_URL", "")
PASSWORD_RESET_TIMEOUT = 60 * 60
EMAIL_BACKEND = os.environ.get("EMAIL_BACKEND", "django.core.mail.backends.smtp.EmailBackend")
EMAIL_HOST = os.environ.get("EMAIL_HOST", "")
EMAIL_PORT = int(os.environ.get("EMAIL_PORT", "587"))
EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = os.environ.get("EMAIL_USE_TLS", "true").lower() in {"1", "true", "yes"}
EMAIL_USE_SSL = os.environ.get("EMAIL_USE_SSL", "false").lower() in {"1", "true", "yes"}
EMAIL_TIMEOUT = 15
DEFAULT_FROM_EMAIL = os.environ.get("DEFAULT_FROM_EMAIL", "")

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

# Comma-separated usernames that should automatically receive staff/admin
# privileges on registration (and when visiting authenticated views).
# Example:
#   C_LARA_BOOTSTRAP_ADMINS=alice,bob
BOOTSTRAP_ADMIN_USERNAMES = [
    name.strip()
    for name in os.environ.get("C_LARA_BOOTSTRAP_ADMINS", "admin").split(",")
    if name.strip()
]

CREDITS_ENABLED = os.environ.get("C_LARA_CREDITS_ENABLED", "1").lower() not in {"0", "false", "no"}
CREDITS_MIN_BALANCE_USD = os.environ.get("C_LARA_CREDITS_MIN_BALANCE_USD", "0.0500")
OPENAI_TOKEN_PRICING_USD_PER_1M = {
    "gpt-6-sol": {"input": "2.00", "output": "10.00"},
    # Default fallback used when a model-specific entry is not configured.
    "default": {"input": "5.00", "output": "15.00"},
    # Override these via local settings/environment-specific patch as needed.
    "gpt-4o": {"input": "5.00", "output": "15.00"},
    "gpt-4o-mini": {"input": "0.15", "output": "0.60"},
    "gpt-5": {"input": "1.25", "output": "10.00"},
    "gpt-5.3-codex": {"input": "1.75", "output": "14.00"},
    "gpt-5.2-codex": {"input": "1.75", "output": "14.00"},
    "gpt-5.1-codex-max": {"input": "1.25", "output": "10.00"},
    "gpt-5.1-codex": {"input": "1.25", "output": "10.00"},
}
OPENAI_PRICING_TRACKED_MODELS = [
    "gpt-4o",
    "gpt-4o-mini",
    "gpt-5",
    "gpt-image-1",
    "gpt-image-2",
    "gpt-5.3-codex",
    "gpt-5.2-codex",
    "gpt-5.1-codex-max",
    "gpt-5.1-codex",
]
OPENAI_PRICING_AI_MODEL = os.environ.get("C_LARA_OPENAI_PRICING_AI_MODEL", "gpt-5")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
# Optional community photo learning; each dictionary must also opt in.
COMMUNITY_DICTIONARY_PHOTO_MODEL = os.environ.get("C_LARA_COMMUNITY_PHOTO_MODEL", "gpt-6-sol")
COMMUNITY_DICTIONARY_PHOTO_DAILY_LIMIT = int(os.environ.get("C_LARA_COMMUNITY_PHOTO_DAILY_LIMIT", "20"))
COMMUNITY_DICTIONARY_TTS_DAILY_LIMIT = int(os.environ.get("C_LARA_COMMUNITY_TTS_DAILY_LIMIT", "20"))
# Server ceiling: shared dictionary allowances default to 10 and are owner-configurable.
# Also caps one account's combined picture descriptions across dictionaries in 24h.
COMMUNITY_DICTIONARY_CAPTURE_DAILY_LIMIT = int(os.environ.get("C_LARA_COMMUNITY_CAPTURE_DAILY_LIMIT", "1000"))
PROJECT_UNDERSTANDING_CODEX_EXECUTABLE = os.environ.get("C_LARA_CODEX_EXECUTABLE", "codex")
PROJECT_UNDERSTANDING_REPOSITORY_PATH = os.environ.get("C_LARA_PROJECT_UNDERSTANDING_REPO", str(ROOT_DIR))
PROJECT_UNDERSTANDING_MODEL = os.environ.get("C_LARA_PROJECT_UNDERSTANDING_MODEL", "gpt-5.3-codex")
PROJECT_UNDERSTANDING_TIMEOUT_SECONDS = float(os.environ.get("C_LARA_PROJECT_UNDERSTANDING_TIMEOUT_SECONDS", "300"))
PROJECT_MANAGER_GROUP_NAME = os.environ.get("C_LARA_PROJECT_MANAGER_GROUP", "project_manager_collaborators")
try:
    PROJECT_MANAGER_COLLABORATOR_ROLES = json.loads(os.environ.get("C_LARA_PROJECT_MANAGER_COLLABORATOR_ROLES", "{}"))
except json.JSONDecodeError:
    PROJECT_MANAGER_COLLABORATOR_ROLES = {}
PROJECT_UNDERSTANDING_GITHUB_BLOB_BASE_URL = os.environ.get(
    "C_LARA_PROJECT_UNDERSTANDING_GITHUB_BLOB_BASE_URL",
    "https://github.com/mannyrayner/C-LARA-2/blob/main",
)

# Optional admin-only legacy C-LARA corpus import support.
# Point this at a server-side folder containing numbered legacy bundle directories
# and a global metadata JSON file produced by the
# build_legacy_bundle_metadata management command.
LEGACY_CLARA_BUNDLE_LIBRARY_ROOT = os.environ.get("C_LARA_LEGACY_BUNDLE_LIBRARY_ROOT", "")
LEGACY_CLARA_BUNDLE_LIBRARY_METADATA = os.environ.get(
    "C_LARA_LEGACY_BUNDLE_LIBRARY_METADATA", "legacy_bundle_metadata.json"
)
