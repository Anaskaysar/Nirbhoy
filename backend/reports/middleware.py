"""
Remove the client's IP address from every request before any view, log or
library can see it.

Rate limiting still needs some way to tell clients apart, so we keep only a
keyed hash of the IP that changes every day. It is held in memory by the
throttle cache for at most an hour and is never written to the database.
"""

import datetime
import hashlib
import hmac

from django.conf import settings

IDENTIFYING_HEADERS = (
    "REMOTE_ADDR",
    "HTTP_X_FORWARDED_FOR",
    "HTTP_X_REAL_IP",
    "HTTP_CF_CONNECTING_IP",
    "HTTP_TRUE_CLIENT_IP",
    "HTTP_FORWARDED",
)


def _daily_client_key(ip: str) -> str:
    day = datetime.date.today().isoformat()
    secret = f"{settings.SECRET_KEY}:{day}".encode()
    return hmac.new(secret, ip.encode(), hashlib.sha256).hexdigest()[:32]


class StripClientIdentityMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
        ip = forwarded.split(",")[0].strip() or request.META.get("REMOTE_ADDR", "")
        request.META["NIRBHOY_CLIENT_KEY"] = _daily_client_key(ip or "unknown")
        for header in IDENTIFYING_HEADERS:
            request.META.pop(header, None)
        # Django expects REMOTE_ADDR to exist; give it a meaningless value.
        request.META["REMOTE_ADDR"] = "0.0.0.0"
        return self.get_response(request)
