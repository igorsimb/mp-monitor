import os
from pathlib import Path
from django.contrib.messages import constants as message_constants
from django.utils import timezone
from environs import Env

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

env = Env()
env.read_env()

ALLOWED_HOSTS = ["*"]

DEBUG = env.bool("DEBUG", default=False)
LOCAL_DEVELOPMENT = env.bool("LOCAL_DEVELOPMENT", default=False)
SECRET_KEY = env("SECRET_KEY", default="CHANGEME")


# Application definition

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.sites",
    "django.contrib.humanize",
    # Third-party
    "django_extensions",
    "debug_toolbar",
    "allauth",
    "allauth.account",
    "allauth.socialaccount",
    "widget_tweaks",
    "guardian",
    "django_celery_beat",
    "sentry",
    # Local
    "main.apps.MainConfig",
    "accounts.apps.AccountsConfig",
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

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
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
    STATIC_ROOT = BASE_DIR / "static"

# Default primary key field type
# https://docs.djangoproject.com/en/3.2/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

AUTH_USER_MODEL = "accounts.CustomUser"

# django-debug-toolbar
INTERNAL_IPS = [
    "127.0.0.1",
]

# django-allauth config
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
# EMAIL_BACKEND = "django.main.mail.backends.console.EmailBackend"
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
ACCOUNT_SESSION_REMEMBER = None  # True/False/None; None = ask user
ACCOUNT_USERNAME_REQUIRED = False
ACCOUNT_AUTHENTICATION_METHOD = "email"
ACCOUNT_EMAIL_REQUIRED = True
ACCOUNT_UNIQUE_EMAIL = True

# REDIS-related settings
REDIS_HOST = "127.0.0.1"
REDIS_PORT = "6379"
CELERY_BROKER_URL = "redis://" + REDIS_HOST + ":" + REDIS_PORT + "/0"
CELERY_BROKER_TRANSPORT_OPTIONS = {"visibility_timout": 3600}
CELERY_RESULT_BACKEND = "redis://" + REDIS_HOST + ":" + REDIS_PORT + "/0"

# new
# CELERY_BROKER_URL = "redis://redis:6379"
# CELERY_RESULT_BACKEND = "redis://redis:6379"
# end new

CELERY_ACCEPT_CONTENT = ["application/json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"

# let celery know to use our new scheduler when running celery beat
CELERY_BEAT_SCHEDULER = "django_celery_beat.schedulers:DatabaseScheduler"


# LOGGING settings


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

# sentry-sdk
SENTRY_ENABLED = env.bool("SENTRY_ENABLED", default=True)
SENTRY_DSN = env("SENTRY_DSN")
