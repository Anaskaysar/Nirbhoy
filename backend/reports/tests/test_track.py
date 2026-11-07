"""Report tracking."""

from .helpers import BaseAPITest


class TrackReportTests(BaseAPITest):
    def setUp(self):
        super().setUp()
        self.code = self.submit().json()["receipt_code"]

    def test_track_with_code_returns_status(self):  # FR-2.1
        r = self.client.get(f"/api/reports/track/{self.code}/")
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertEqual(body["status"], "pending")
        self.assertEqual(body["district"], "Dhaka")

    def test_tracking_never_shows_report_text(self):  # FR-2.2
        body = self.client.get(f"/api/reports/track/{self.code}/").json()
        for hidden in ("title", "description", "area", "id"):
            self.assertNotIn(hidden, body)

    def test_code_works_in_lowercase_and_without_dashes(self):  # FR-2.3
        compact = self.code.replace("-", "").lower()
        self.assertEqual(self.client.get(f"/api/reports/track/{compact}/").status_code, 200)

    def test_code_without_prefix_works(self):  # FR-2.3
        self.assertEqual(self.client.get(f"/api/reports/track/{self.code[3:]}/").status_code, 200)

    def test_unknown_code_returns_404(self):  # FR-2.4
        r = self.client.get("/api/reports/track/NB-2222-3333-4444/")
        self.assertErrorShape(r, 404, "not_found")

    def test_malformed_code_returns_same_404(self):  # FR-2.4
        unknown = self.client.get("/api/reports/track/NB-2222-3333-4444/").json()
        malformed = self.client.get("/api/reports/track/hello/").json()
        self.assertEqual(unknown, malformed)
