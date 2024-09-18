"""
Custom email backend for Django.
Source: https://stackoverflow.com/questions/75269008/getting-ssl-error-when-sending-email-via-django
How to use:
in settings.py:
EMAIL_BACKEND = "notifier.email.EmailBackend"

WARNING! This disables hostname verification, which is a security risk. Avoid using it in production if possible.

"""

import ssl

from django.core.mail.backends.smtp import EmailBackend as SMTPBackend
from django.utils.functional import cached_property


class EmailBackend(SMTPBackend):
    @cached_property
    def ssl_context(self):
        if self.ssl_certfile or self.ssl_keyfile:
            ssl_context = ssl.SSLContext(protocol=ssl.PROTOCOL_TLS_CLIENT)
            ssl_context.load_cert_chain(self.ssl_certfile, self.ssl_keyfile)
            return ssl_context
        else:
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE
            return ssl_context
