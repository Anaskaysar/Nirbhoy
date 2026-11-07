"""Report review and audit trail."""

from reports.models import Report, ReviewAction

from .helpers import BaseAPITest

VERIFY = {
    "decision": "verify",
    "note": "Matches another report.",
    "public_summary": "Citizens report unofficial cash fees at a Savar land office.",
}


class ReviewAccessTests(BaseAPITest):
    def setUp(self):
        super().setUp()
        self.submit()
        self.report = Report.objects.get()

    def test_no_token_returns_401(self):  # NFR-8
        self.assertErrorShape(self.client.get("/api/review/reports/"), 401, "not_authenticated")

    def test_bad_token_returns_401(self):  # NFR-8
        self.client.credentials(HTTP_AUTHORIZATION="Token not-a-real-token")
        self.assertErrorShape(self.client.get("/api/review/reports/"), 401, "authentication_failed")

    def test_non_reviewer_returns_403(self):  # NFR-8
        self.as_outsider()
        self.assertErrorShape(self.client.get("/api/review/reports/"), 403, "permission_denied")

    def test_non_reviewer_cannot_decide(self):  # NFR-8
        self.as_outsider()
        r = self.client.patch(f"/api/review/reports/{self.report.id}/", VERIFY, format="json")
        self.assertErrorShape(r, 403, "permission_denied")
        self.report.refresh_from_db()
        self.assertEqual(self.report.status, "pending")


class ReviewListTests(BaseAPITest):
    def setUp(self):
        super().setUp()
        self.submit()
        self.submit(category="healthcare", district="Rangpur", title="Free medicine being sold",
                    description="Free government medicine is sold to patients outside the hospital gate.")
        self.as_reviewer()

    def test_reviewer_sees_full_report_text(self):  # FR-4.1, FR-4.2
        r = self.client.get("/api/review/reports/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["count"], 2)
        self.assertIn("title", r.json()["results"][0])

    def test_filter_by_category_and_district(self):  # FR-4.1
        r = self.client.get("/api/review/reports/?category=healthcare&district=rangpur")
        self.assertEqual(r.json()["count"], 1)

    def test_invalid_status_filter_returns_400(self):  # NFR-11
        self.assertErrorShape(self.client.get("/api/review/reports/?status=maybe"), 400, "validation_error")

    def test_detail_includes_description_and_history(self):  # FR-4.2
        rid = Report.objects.first().id
        body = self.client.get(f"/api/review/reports/{rid}/").json()
        self.assertIn("description", body)
        self.assertEqual(body["review_history"], [])

    def test_unknown_report_returns_404(self):
        self.assertErrorShape(self.client.get("/api/review/reports/99999/"), 404, "not_found")


class ReviewDecisionTests(BaseAPITest):
    def setUp(self):
        super().setUp()
        self.code = self.submit().json()["receipt_code"]
        self.report = Report.objects.get()
        self.url = f"/api/review/reports/{self.report.id}/"
        self.as_reviewer()

    def test_verify_requires_public_summary(self):  # FR-4.4
        err = self.assertErrorShape(self.client.patch(self.url, {"decision": "verify"}, format="json"),
                                    400, "validation_error")
        self.assertIn("public_summary", err["details"])

    def test_reject_requires_note(self):  # FR-4.5
        err = self.assertErrorShape(self.client.patch(self.url, {"decision": "reject"}, format="json"),
                                    400, "validation_error")
        self.assertIn("note", err["details"])

    def test_verify_updates_status_and_writes_audit_record(self):  # FR-4.3, FR-4.7
        r = self.client.patch(self.url, VERIFY, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        self.report.refresh_from_db()
        self.assertEqual(self.report.status, "verified")
        self.assertEqual(self.report.public_summary, VERIFY["public_summary"])
        self.assertIsNotNone(self.report.reviewed_at)
        action = ReviewAction.objects.get()
        self.assertEqual((action.reviewer, action.decision), (self.reviewer, "verify"))
        self.assertEqual(r.json()["review_history"][0]["reviewer"], "rev")

    def test_reject_works_with_note(self):  # FR-4.3, FR-4.5
        r = self.client.patch(self.url, {"decision": "reject", "note": "No specific office."}, format="json")
        self.assertEqual(r.status_code, 200)
        self.report.refresh_from_db()
        self.assertEqual(self.report.status, "rejected")
        self.assertEqual(self.report.public_summary, "")

    def test_second_review_returns_409(self):  # FR-4.6
        self.client.patch(self.url, VERIFY, format="json")
        r = self.client.patch(self.url, {"decision": "reject", "note": "Changed my mind."}, format="json")
        self.assertErrorShape(r, 409, "conflict")
        self.assertEqual(ReviewAction.objects.count(), 1)

    def test_reporter_sees_result_and_message_when_tracking(self):  # FR-4.8, FR-2.1
        self.client.patch(self.url, {**VERIFY, "reviewer_message": "Thanks, this helped."}, format="json")
        self.anonymous()
        body = self.client.get(f"/api/reports/track/{self.code}/").json()
        self.assertEqual(body["status"], "verified")
        self.assertEqual(body["reviewer_message"], "Thanks, this helped.")

    def test_default_reviewer_message_is_used(self):  # FR-4.8
        self.client.patch(self.url, VERIFY, format="json")
        self.report.refresh_from_db()
        self.assertTrue(self.report.reviewer_message)
