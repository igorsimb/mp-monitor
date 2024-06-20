import os
from pathlib import Path

import environ
from django.contrib.messages import constants as message_constants
from django.utils import timezone

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# defaults
env = environ.Env(
    ALLOWED_HOSTS=(list, []),
    DEBUG=(bool, False),
    CSRF_COOKIE_SECURE=(bool, True),
    LOCAL_DEVELOPMENT=(bool, False),
    SECURE_HSTS_SECONDS=(int, 60 * 60 * 24 * 365),  # 1 year
    SECURE_SSL_REDIRECT=(bool, True),
    SESSION_COOKIE_SECURE=(bool, True),
    SENTRY_ENABLED=(bool, True),
)
environ.Env.read_env(BASE_DIR / ".env")


SECRET_KEY = env("SECRET_KEY")
DEBUG = env("DEBUG")
ALLOWED_HOSTS = ["mpmonitor.ru", "www.mpmonitor.ru", "127.0.4.47:58322", "localhost", "127.0.0.1"]
LOCAL_DEVELOPMENT = env("LOCAL_DEVELOPMENT")


# Application definition

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.humanize",
    "django.contrib.messages",
    "django.contrib.sessions",
    "django.contrib.sites",
    "django.contrib.staticfiles",
    # Third-party
    "allauth",
    "allauth.account",
    "allauth.socialaccount",
    "anymail",
    "debug_toolbar",
    "django_celery_beat",
    "django_extensions",
    "django_htmx",
    "guardian",
    "simple_history",
    "widget_tweaks",
    # Local
    "accounts.apps.AccountsConfig",
    "main.apps.MainConfig",
    "sentry",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "debug_toolbar.middleware.DebugToolbarMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "allauth.account.middleware.AccountMiddleware",
    "django_htmx.middleware.HtmxMiddleware",
]

ROOT_URLCONF = "mp_monitor.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        # if use default [], it will redirect to allauth's login, signup, etc as opposed to our "accounts" app
        "DIRS": [os.path.join(BASE_DIR, "accounts", "templates")],
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

WSGI_APPLICATION = "mp_monitor.wsgi.application"

# Database
# https://docs.djangoproject.com/en/3.2/ref/settings/#databases

if LOCAL_DEVELOPMENT:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
            # for sqlite write lock timeout
            "OPTIONS": {
                "timeout": 5,
            },
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "HOST": os.environ["DBHOST"],
            "NAME": os.environ["DBNAME"],
            "USER": os.environ["DBUSER"],
            "PASSWORD": os.environ["DBPASS"],
            "PORT": "5432",
        },
    }

# Password validation
# https://docs.djangoproject.com/en/3.2/ref/settings/#auth-password-validators

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
# https://docs.djangoproject.com/en/3.2/topics/i18n/

LANGUAGE_CODE = "ru-ru"

TIME_ZONE = "Europe/Moscow"

USE_I18N = True


USE_TZ = True

# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/3.2/howto/static-files/

STATIC_URL = "/static/"
STATIC_DIR = [BASE_DIR / "static"]

if LOCAL_DEVELOPMENT:
    STATICFILES_DIRS = [BASE_DIR / "static"]
else:
    STATIC_ROOT = env("STATIC_ROOT")

# Default primary key field type
# https://docs.djangoproject.com/en/3.2/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

AUTH_USER_MODEL = "accounts.CustomUser"

# Email

EMAIL_BACKEND = env("EMAIL_BACKEND", default="anymail.backends.sendgrid.EmailBackend")
DEFAULT_FROM_FIELD = "noreply@mpmonitor.ru"
SERVER_EMAIL = "noreply@mpmonitor.ru"


# LOGGING


# Generate log file paths based on year and month
def log_file_path(instance, filename):  # pylint: disable=unused-argument
    today = timezone.now()
    log_dir = os.path.join("logs", str(today.year), today.strftime("%B"))
    os.makedirs(log_dir, exist_ok=True)  # Create the directory if it doesn't exist
    return os.path.join("logs", str(today.year), today.strftime("%B"), filename)


LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "filters": {
        "require_debug_false": {
            "()": "django.utils.log.RequireDebugFalse",
        },
        "require_debug_true": {
            "()": "django.utils.log.RequireDebugTrue",
        },
    },
    "formatters": {
        "verbose": {
            "format": "[%(levelname)s] %(asctime)s - %(name)s:%(lineno)s - %(message)s",
        },
    },
    "handlers": {
        "debug_log": {
            "level": "DEBUG",
            "class": "logging.handlers.RotatingFileHandler",
            "filename": log_file_path(None, "debug.log"),
            "maxBytes": 1024 * 1024 * 5,  # 5MB
            "backupCount": 5,
            "formatter": "verbose",  # Use the custom formatter, see above
            "encoding": "utf-8",
        },
        "error_log": {
            "level": "ERROR",
            "class": "logging.handlers.RotatingFileHandler",
            "filename": log_file_path(None, "error.log"),
            "maxBytes": 1024 * 1024 * 5,  # 5MB
            "backupCount": 5,
            "formatter": "verbose",
            "encoding": "utf-8",
        },
        "info_log": {
            "level": "INFO",
            "class": "logging.handlers.RotatingFileHandler",
            "filename": log_file_path(None, "info.log"),
            "maxBytes": 1024 * 1024 * 5,  # 5MB
            "backupCount": 5,
            "formatter": "verbose",
            "encoding": "utf-8",
        },
        "console": {
            "level": "INFO",
            "filters": ["require_debug_true"],
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
    },
    "loggers": {
        "": {
            # "handlers": ["info_log", "console"],
            "handlers": ["console"],
            "level": "INFO",
            "propagate": True,
        },
        # "django": {
        #     "handlers": ["error_log"],
        #     "level": "DEBUG",
        #     "propagate": True,
        # },
    },
}

# Django Messages settings
# Instead of "error" we use "danger" to indicate a bootstrap class
# Source: https://docs.djangoproject.com/en/4.2/ref/settings/#message-tags
MESSAGE_TAGS = {message_constants.ERROR: "danger"}

# django-debug-toolbar
INTERNAL_IPS = [
    "127.0.0.1",
]

# django-allauth

SITE_ID = 1
LOGIN_REDIRECT_URL = "item_list"
ACCOUNT_LOGOUT_REDIRECT = "item_list"
# point to a custom sign up form
# ACCOUNT_FORMS = {'signup': 'accounts.forms.CustomUserCreationForm'}
AUTHENTICATION_BACKENDS = (
    "django.contrib.auth.backends.ModelBackend",
    "allauth.account.auth_backends.AuthenticationBackend",
    "guardian.backends.ObjectPermissionBackend",
)

ACCOUNT_SESSION_REMEMBER = True  # True/False/None; None = ask user
ACCOUNT_USERNAME_REQUIRED = False
ACCOUNT_AUTHENTICATION_METHOD = "email"
ACCOUNT_EMAIL_REQUIRED = True
ACCOUNT_UNIQUE_EMAIL = True

# REDIS-related settings
if LOCAL_DEVELOPMENT:
    REDIS_HOST = "127.0.0.1"
    REDIS_PORT = "6379"
    CELERY_BROKER_URL = "redis://" + REDIS_HOST + ":" + REDIS_PORT + "/0"
    CELERY_RESULT_BACKEND = "redis://" + REDIS_HOST + ":" + REDIS_PORT + "/0"
else:
    CELERY_BROKER_URL = "redis://localhost:6379"
    CELERY_RESULT_BACKEND = "django-db"

CELERY_TIMEZONE = "Europe/Moscow"
CELERY_BROKER_TRANSPORT_OPTIONS = {"visibility_timout": 3600}
CELERY_ACCEPT_CONTENT = ["application/json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"

# let celery know to use our new scheduler when running celery beat
CELERY_BEAT_SCHEDULER = "django_celery_beat.schedulers:DatabaseScheduler"


# django-anymail
ANYMAIL = {
    "SENDGRID_API_KEY": env("SENDGRID_API_KEY"),
}
EMAIL_SENDGRID_REPLY_TO = env("EMAIL_SENDGRID_REPLY_TO")


# Security
CSRF_COOKIE_SECURE = env("CSRF_COOKIE_SECURE")
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_HSTS_SECONDS = env("SECURE_HSTS_SECONDS")
SECURE_SSL_REDIRECT = env("SECURE_SSL_REDIRECT")
SESSION_COOKIE_SECURE = env("SESSION_COOKIE_SECURE")

#  django deploy check is not recognizing the correct SECRET_KEY from .env, silencing this warning
SILENCED_SYSTEM_CHECKS: list[str] = ["security.W009"]


# sentry-sdk
SENTRY_ENABLED = env("SENTRY_ENABLED")
SENTRY_DSN = env("SENTRY_DSN")

# rate limiting
RATELIMIT_ENABLE = True  # set to False to disable all rate limiting
