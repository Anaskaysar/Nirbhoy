"""Public data."""

from reports.models import Report

from .helpers import BaseAPITest


class PublicDataTests(BaseAPITest):
    def setUp(self):
        super().setUp()
        self.submit()  # stays pending
        self.submit(category="healthcare", district="Rangpur", title="Free medicine being sold",
                    description="Free government medicine is sold to patients outside the hospital gate.")
        self.submit(category="education", district="Cumilla", title="Stipend never received",
                    description="Students say their stipend was recorded as paid but never reached them.")
        healthcare, education = Report.objects.filter(category__in=["healthcare", "education"]).order_by("id")
        self.as_reviewer()
        self.client.patch(f"/api/review/reports/{healthcare.id}/", {
            "decision": "verify", "public_summary": "Free medicines reported sold at a Rangpur health complex."
        }, format="json")
        self.client.patch(f"/api/review/reports/{education.id}/", {"decision": "reject", "note": "Too vague."}, format="json")
        self.anonymous()

    def test_only_verified_reports_are_public(self):  # FR-5.1
        body = self.client.get("/api/public/reports/").json()
        self.assertEqual(body["count"], 1)
        self.assertEqual(body["results"][0]["district"], "Rangpur")

    def test_public_reports_hide_raw_text_and_internal_id(self):  # FR-5.1
        item = self.client.get("/api/public/reports/").json()["results"][0]
        self.assertEqual(set(item), {"id", "category", "category_label", "district", "public_summary", "verified_on"})
        internal_id = Report.objects.get(status="verified").id
        self.assertNotEqual(item["id"], internal_id)  # UUID, not the database id

    def test_public_filter_by_district(self):  # FR-5.1
        self.assertEqual(self.client.get("/api/public/reports/?district=Dhaka").json()["count"], 0)
        self.assertEqual(self.client.get("/api/public/reports/?district=rangpur").json()["count"], 1)

    def test_stats_match_database(self):  # FR-5.2
        s = self.client.get("/api/public/stats/").json()
        self.assertEqual((s["total_received"], s["pending"], s["verified"], s["rejected"]), (3, 1, 1, 1))
        self.assertEqual(s["verified_by_category"][0]["key"], "healthcare")

    def test_meta_lists_all_64_districts(self):  # FR-5.3
        m = self.client.get("/api/meta/").json()
        self.assertEqual(len(m["districts"]), 64)
        self.assertEqual(len(m["categories"]), 8)

    def test_health(self):  # FR-5.4
        self.assertEqual(self.client.get("/api/health/").json(), {"status": "ok"})

    def test_swagger_docs_and_schema_load(self):  # NFR-9
        self.assertEqual(self.client.get("/api/docs/").status_code, 200)
        self.assertEqual(self.client.get("/api/schema/").status_code, 200)
