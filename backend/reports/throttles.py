from rest_framework.throttling import SimpleRateThrottle


class _HashedClientThrottle(SimpleRateThrottle):
    """
    Rate limit by the daily-rotating hashed key set in
    StripClientIdentityMiddleware, never by the raw IP address.
    """

    def get_cache_key(self, request, view):
        key = request.META.get("NIRBHOY_CLIENT_KEY", "unknown")
        return self.cache_format % {"scope": self.scope, "ident": key}


class ReportSubmitThrottle(_HashedClientThrottle):
    scope = "report_submit"  # stops one person flooding the system


class ReportTrackThrottle(_HashedClientThrottle):
    scope = "report_track"  # stops brute-force guessing of receipt codes
