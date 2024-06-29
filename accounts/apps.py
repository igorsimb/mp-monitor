from django.apps import AppConfig
# from django.core.signals import request_finished


class AccountsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "accounts"

    # def ready(self):  # pragma: no cover

    # from . import signals
    # TODO: use real function names instead of signals.function_from_signals_1 and 2, give them unique dispatch_uids
    # https://docs.djangoproject.com/en/5.0/topics/signals/#preventing-duplicate-signals
    # request_finished.connect(signals.function_from_signals_1, dispatch_uid="accounts_callback_one")
    # request_finished.connect(signals.function_from_signals_2, dispatch_uid="accounts_callback_two")
