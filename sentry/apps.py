import sentry_sdk
from django.apps import AppConfig

from django.conf import settings


def traces_sampler(sampling_context):  # pragma: no cover
    """Select a sample rate off of the requested path. Returns

    The root endpoint seemed to get hammered by some bot and ate a huge percent of transactions in a week.
    I don't care about that page right now, so ignore it.
    """
    path = sampling_context.get("wsgi_environ", {}).get("PATH_INFO", "")
    if path == "/":
        return 0

    return 1.0


class SentryConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "sentry"

    def ready(self):  # pragma: no cover
        """Initialize Sentry.

        Sentry initialization is moved to an application ready timeframe because it triggers circular imports
        with settings when used with type checking when django-stubs is enabled.
        """
        sentry_enabled = getattr(settings, "SENTRY_ENABLED", False)
        if not sentry_enabled:
            return

        sentry_sdk.init(
            # dsn="https://7069b1f9ca6f668d6ffd95c24219eb85@o4506855689289728.ingest.us.sentry.io/4506855719043072",
            dsn=settings.SENTRY_DSN,
            # Set traces_sample_rate to 1.0 to capture 100%
            # of transactions for performance monitoring.
            # traces_sample_rate=1.0,
            # Set profiles_sample_rate to 1.0 to profile 100%
            # of sampled transactions.
            # We recommend adjusting this value in production.
            profiles_sample_rate=1.0,
            traces_sampler=traces_sampler,  # replaces line: traces_sample_rate=1.0
            # Associate users to errors
            send_default_pii=True,
        )
