"""
Django settings for the Nirbhoy API.

Secrets come from environment variables. The fallbacks below are for local
development only and must be replaced in production (see README, "Deploy").
"""

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# ---------------------------------------------------------------------------
# Core
# ---------------------------------------------------------------------------

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "dev-only-insecure-key-change-me-in-production")
DEBUG = os.environ.get("DJANGO_DEBUG", "true").lower() == "true"
ALLOWED_HOSTS = os.environ.get("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")
CSRF_TRUSTED_ORIGINS = [o for o in os.environ.get("DJANGO_CSRF_TRUSTED_ORIGINS", "").split(",") if o]

# Key used to encrypt report text at rest (Fernet = AES-128-CBC + HMAC-SHA256).
# Generate a real one with:
#   python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
FIELD_ENCRYPTION_KEY = os.environ.get(
    "FIELD_ENCRYPTION_KEY", "Zm9yLWRldmVsb3BtZW50LW9ubHktMzItYnl0ZXMhISE="
)

# Key for hashing receipt codes. Kept separate from SECRET_KEY so rotating
# SECRET_KEY does not make every existing receipt code stop working.
RECEIPT_HASH_KEY = os.environ.get("RECEIPT_HASH_KEY", "dev-only-receipt-hash-key")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "rest_framework.authtoken",
    "drf_spectacular",
    "drf_spectacular_sidecar",  # serves Swagger UI files locally (no CDN needed)
    "reports",
]

MIDDLEWARE = [
    # First, so no other code ever sees the client's IP address.
    "reports.middleware.StripClientIdentityMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

# WhiteNoise serves static files in production only. Locally, runserver
# serves them itself, and the staticfiles folder does not exist yet.
if DEBUG:
    MIDDLEWARE.remove("whitenoise.middleware.WhiteNoiseMiddleware")

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": os.environ.get("SQLITE_PATH", BASE_DIR / "db.sqlite3"),
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "Asia/Dhaka"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

# Evidence photos. Never served from a public URL (see AttachmentDownloadView).
MEDIA_ROOT = Path(os.environ.get("MEDIA_ROOT", BASE_DIR / "media"))

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Reject request bodies larger than 20 MB (3 photos x 5 MB + form fields).
DATA_UPLOAD_MAX_MEMORY_SIZE = 20 * 1024 * 1024

# ---------------------------------------------------------------------------
# Django REST Framework
# ---------------------------------------------------------------------------

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": ["rest_framework.authentication.TokenAuthentication"],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.AllowAny"],
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 20,
    "EXCEPTION_HANDLER": "reports.exceptions.api_exception_handler",
    "DEFAULT_THROTTLE_RATES": {
        "report_submit": os.environ.get("SUBMIT_RATE", "5/hour"),
        "report_track": os.environ.get("TRACK_RATE", "30/minute"),
    },
}

# ---------------------------------------------------------------------------
# Swagger / OpenAPI
# ---------------------------------------------------------------------------

SPECTACULAR_SETTINGS = {
    "TITLE": "Nirbhoy API",
    "DESCRIPTION": (
        "**Nirbhoy (নির্ভয়) means fearless.** Anonymous reporting of corruption and "
        "public-service problems in Bangladesh, with human verification before anything "
        "is published.\n\n"
        "### Try it in this order\n"
        "1. **Submit** a report with `POST /api/reports/`. Copy the `receipt_code` it returns.\n"
        "2. **Track** it with `GET /api/reports/track/{receipt_code}/`.\n"
        "3. **Log in** as a reviewer with `POST /api/auth/login/` "
        "(demo: `reviewer` / `review-demo-2026`). Click **Authorize** and enter `Token <your token>`.\n"
        "4. **Review**: list with `GET /api/review/reports/`, then verify or reject with "
        "`PATCH /api/review/reports/{id}/`.\n"
        "5. **See it public** with `GET /api/public/reports/` and `GET /api/public/stats/`.\n\n"
        "### Privacy by design\n"
        "No reporter accounts. No IP addresses stored. Receipt codes stored only as a keyed hash. "
        "Report text encrypted at rest. Submission time rounded to the hour. "
        "Photo location data (EXIF/GPS) removed.\n\n"
        "### Errors\n"
        "Every error has the same shape: "
        "`{\"error\": {\"status\", \"code\", \"message\", \"details\"}}`."
    ),
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "COMPONENT_SPLIT_REQUEST": True,
    "SWAGGER_UI_DIST": "SIDECAR",
    "SWAGGER_UI_FAVICON_HREF": "/static/nirbhoy/logo.svg",
    "REDOC_DIST": "SIDECAR",
    "SWAGGER_UI_SETTINGS": {
        "persistAuthorization": True,
        "displayRequestDuration": True,
        "docExpansion": "list",
        "defaultModelsExpandDepth": 0,
        "tryItOutEnabled": True,
    },
    "TAGS": [
        {"name": "Reporting", "description": "Anonymous citizen endpoints. No login."},
        {"name": "Auth", "description": "Reviewer login."},
        {"name": "Reviewer", "description": "Verified reviewers only (token required)."},
        {"name": "Public", "description": "Verified, published data only."},
    ],
}

# ---------------------------------------------------------------------------
# Logging: never write client IPs. Request access lines are suppressed.
# ---------------------------------------------------------------------------

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "loggers": {
        "django.server": {"handlers": ["console"], "level": "WARNING", "propagate": False},
        "django.request": {"handlers": ["console"], "level": "ERROR", "propagate": False},
    },
}

if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    STORAGES = {
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
    }
