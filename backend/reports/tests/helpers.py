from django.contrib.auth.models import Group, User
from django.core.cache import cache
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from reports.permissions import REVIEWER_GROUP

VALID_REPORT = {
    "category": "bribery",
    "district": "Dhaka",
    "area": "Savar AC Land Office",
    "title": "Cash demanded for land mutation",
    "description": "An office assistant asked for 15,000 taka in cash to process a land mutation. No receipt was given.",
}


class BaseAPITest(APITestCase):
    """Shared setup: clean rate-limit cache, a reviewer and a normal user."""

    def setUp(self):
        cache.clear()  # rate-limit counters live in the cache
        group, _ = Group.objects.get_or_create(name=REVIEWER_GROUP)
        self.reviewer = User.objects.create_user("rev", password="Strong-pass-123")
        self.reviewer.groups.add(group)
        self.outsider = User.objects.create_user("bob", password="Strong-pass-123")
        self.reviewer_token = Token.objects.create(user=self.reviewer).key
        self.outsider_token = Token.objects.create(user=self.outsider).key

    def submit(self, **overrides):
        return self.client.post("/api/reports/", {**VALID_REPORT, **overrides}, format="json")

    def as_reviewer(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.reviewer_token}")

    def as_outsider(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.outsider_token}")

    def anonymous(self):
        self.client.credentials()

    def assertErrorShape(self, response, status, code):
        """Every error response must use the same JSON shape."""
        self.assertEqual(response.status_code, status, response.content)
        body = response.json()
        self.assertIn("error", body)
        self.assertEqual(body["error"]["status"], status)
        self.assertEqual(body["error"]["code"], code)
        self.assertTrue(body["error"]["message"])
        return body["error"]
