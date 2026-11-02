"""
Django settings for mechora project.

Enhanced with Django Unfold Administration, Production-Ready Authentication,
and Enterprise Security Standards.
"""

import os
from pathlib import Path
from django.urls import reverse_lazy

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Load environment variables if .env is present
try:
    from dotenv import load_dotenv
    load_dotenv(BASE_DIR / ".env")
except ImportError:
    pass

# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/6.1/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.environ.get(
    "SECRET_KEY",
    "django-insecure-=$a_qj!hedm-wh)jn_ba!k)g4#r@dz%mu-b&_jh$411c!fre1@",
)

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = os.environ.get("DEBUG", "True").lower() in ("true", "1", "yes")

ALLOWED_HOSTS = [
    host.strip()
    for host in os.environ.get("ALLOWED_HOSTS", "127.0.0.1,localhost,testserver").split(",")
    if host.strip()
]


# Application definition
# Unfold apps MUST precede django.contrib.admin
INSTALLED_APPS = [
    "unfold",
    "unfold.contrib.filters",
    "unfold.contrib.forms",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",

    # Local MECHORA applications
    "accounts.apps.AccountsConfig",
    "assistant.apps.AssistantConfig",
    "dashboard.apps.DashboardConfig",
    "machines.apps.MachinesConfig",
    "manuals.apps.ManualsConfig",
    "rag.apps.RagConfig",
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

ROOT_URLCONF = "mechora.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
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

WSGI_APPLICATION = "mechora.wsgi.application"


# Database
# https://docs.djangoproject.com/en/6.1/ref/settings/#databases

if os.environ.get("POSTGRES_DB"):
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": os.environ["POSTGRES_DB"],
            "USER": os.environ.get("POSTGRES_USER", ""),
            "PASSWORD": os.environ.get("POSTGRES_PASSWORD", ""),
            "HOST": os.environ.get("POSTGRES_HOST", "127.0.0.1"),
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


# Password validation
# https://docs.djangoproject.com/en/6.1/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]


# Internationalization
# https://docs.djangoproject.com/en/6.1/topics/i18n/

LANGUAGE_CODE = "en-us"

TIME_ZONE = "UTC"

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/6.1/howto/static-files/

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

# Media and Document Storage
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"


# Email
# https://docs.djangoproject.com/en/6.1/topics/email/#topic-email-configuration

MAILERS = {
    "default": {
        "BACKEND": "django.core.mail.backends.console.EmailBackend",
    },
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


# Security & Session Hardening
# https://docs.djangoproject.com/en/6.1/topics/security/

SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_AGE = 86400  # 24 hours session lifetime
SESSION_EXPIRE_AT_BROWSER_CLOSE = False
SESSION_SAVE_EVERY_REQUEST = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"

SECURE_SSL_REDIRECT = os.environ.get("SECURE_SSL_REDIRECT", "false").lower() in ("true", "1", "yes")

# Celery uses Redis as the broker/result backend. Override these for a remote
# Redis instance in deployment environments.
CELERY_BROKER_URL = os.environ.get("CELERY_BROKER_URL", "redis://127.0.0.1:6379/0")
CELERY_RESULT_BACKEND = os.environ.get("CELERY_RESULT_BACKEND", CELERY_BROKER_URL)
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_TIME_LIMIT = 30 * 60
CELERY_TASK_ACKS_LATE = True
CELERY_WORKER_PREFETCH_MULTIPLIER = 1

if not DEBUG:
    CSRF_COOKIE_SECURE = True
    SESSION_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 31536000  # 1 year HSTS
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    X_FRAME_OPTIONS = "DENY"
else:
    CSRF_COOKIE_SECURE = False
    SESSION_COOKIE_SECURE = False
    X_FRAME_OPTIONS = "SAMEORIGIN"


# ==============================================================================
# DJANGO UNFOLD CONFIGURATION
# https://github.com/unfoldadmin/django-unfold
# ==============================================================================

UNFOLD = {
    "SITE_TITLE": "MECHORA Administration",
    "SITE_HEADER": "MECHORA",
    "SITE_SUBHEADER": "Industrial Management System",
    "SITE_URL": "/",
    "SHOW_HISTORY": True,
    "SHOW_VIEW_ON_SITE": True,
    "DASHBOARD_CALLBACK": "mechora.admin_dashboard.dashboard_callback",
    "SIDEBAR": {
        "show_search": True,
        "show_all_applications": False,
        "navigation": [
            {
                "title": "MECHORA Administration",
                "separator": True,
                "collapsible": False,
                "items": [
                    {
                        "title": "Dashboard Overview",
                        "icon": "dashboard",
                        "link": reverse_lazy("admin:index"),
                        "permission": "mechora.admin_permissions.can_view_dashboard",
                    },
                ],
            },
            {
                "title": "Equipment & Manuals",
                "separator": True,
                "collapsible": True,
                "items": [
                    {
                        "title": "Machine Management",
                        "icon": "precision_manufacturing",
                        "link": reverse_lazy("admin:machines_machine_changelist"),
                        "permission": "mechora.admin_permissions.can_view_machines",
                    },
                    {
                        "title": "Manual Management",
                        "icon": "menu_book",
                        "link": reverse_lazy("admin:manuals_manual_changelist"),
                        "permission": "mechora.admin_permissions.can_view_manuals",
                    },
                ],
            },
            {
                "title": "RAG & Knowledge System",
                "separator": True,
                "collapsible": True,
                "items": [
                    {
                        "title": "RAG Query Logs",
                        "icon": "psychology",
                        "link": reverse_lazy("admin:rag_ragquerylog_changelist"),
                        "permission": "mechora.admin_permissions.can_view_rag_queries",
                    },
                    {
                        "title": "Document Chunks",
                        "icon": "segment",
                        "link": reverse_lazy("admin:rag_ragdocumentchunk_changelist"),
                        "permission": "mechora.admin_permissions.can_view_rag_chunks",
                    },
                ],
            },
            {
                "title": "Authentication & Security",
                "separator": True,
                "collapsible": True,
                "items": [
                    {
                        "title": "User Accounts",
                        "icon": "person",
                        "link": reverse_lazy("admin:auth_user_changelist"),
                        "permission": "mechora.admin_permissions.can_view_users",
                    },
                    {
                        "title": "Groups & Permissions",
                        "icon": "admin_panel_settings",
                        "link": reverse_lazy("admin:auth_group_changelist"),
                        "permission": "mechora.admin_permissions.can_view_groups",
                    },
                ],
            },
        ],
    },
}
