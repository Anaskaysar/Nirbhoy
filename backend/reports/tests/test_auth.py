"""Reviewer authentication."""

from .helpers import BaseAPITest


class LoginTests(BaseAPITest):
    def test_reviewer_gets_token(self):  # FR-3.1
        r = self.client.post("/api/auth/login/", {"username": "rev", "password": "Strong-pass-123"}, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["token"], self.reviewer_token)

    def test_wrong_password_returns_401(self):  # FR-3.3
        r = self.client.post("/api/auth/login/", {"username": "rev", "password": "nope"}, format="json")
        err = self.assertErrorShape(r, 401, "authentication_failed")
        self.assertNotIn("password", err["message"].split()[0].lower())

    def test_unknown_user_gets_same_message_as_wrong_password(self):  # FR-3.3
        a = self.client.post("/api/auth/login/", {"username": "rev", "password": "nope"}, format="json").json()
        b = self.client.post("/api/auth/login/", {"username": "ghost", "password": "nope"}, format="json").json()
        self.assertEqual(a, b)

    def test_non_reviewer_cannot_log_in(self):  # FR-3.2
        r = self.client.post("/api/auth/login/", {"username": "bob", "password": "Strong-pass-123"}, format="json")
        self.assertErrorShape(r, 403, "permission_denied")

    def test_missing_fields_return_400(self):
        err = self.assertErrorShape(self.client.post("/api/auth/login/", {}, format="json"), 400, "validation_error")
        self.assertIn("username", err["details"])
        self.assertIn("password", err["details"])
