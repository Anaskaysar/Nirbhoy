"""Privacy and security."""

from django.http import HttpResponse
from django.test import RequestFactory, SimpleTestCase

from reports.middleware import StripClientIdentityMiddleware


class StripIpMiddlewareTests(SimpleTestCase):
    def test_ip_headers_are_removed_before_views_run(self):  # NFR-1, NFR-2
        seen = {}

        def view(request):
            seen.update(request.META)
            return HttpResponse("ok")

        request = RequestFactory().get(
            "/", REMOTE_ADDR="203.0.113.7", HTTP_X_FORWARDED_FOR="198.51.100.9", HTTP_X_REAL_IP="198.51.100.9"
        )
        StripClientIdentityMiddleware(view)(request)

        self.assertEqual(seen["REMOTE_ADDR"], "0.0.0.0")
        self.assertNotIn("HTTP_X_FORWARDED_FOR", seen)
        self.assertNotIn("HTTP_X_REAL_IP", seen)
        self.assertNotIn("203.0.113.7", str(seen.values()))

    def test_rate_limit_key_is_a_hash_not_the_ip(self):  # NFR-3
        seen = {}
        request = RequestFactory().get("/", REMOTE_ADDR="203.0.113.7")
        StripClientIdentityMiddleware(lambda r: seen.update(r.META) or HttpResponse())(request)
        key = seen["NIRBHOY_CLIENT_KEY"]
        self.assertEqual(len(key), 32)
        self.assertNotIn("203", key)
