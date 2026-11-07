"""Report submission (core feature)."""

import datetime
import io
import re
from unittest.mock import patch

from django.db import connection
from django.utils import timezone
from PIL import Image

from reports.models import Attachment, Report
from reports.security import hash_receipt_code
from reports.throttles import ReportSubmitThrottle

from .helpers import VALID_REPORT, BaseAPITest

CODE_PATTERN = re.compile(r"^NB-[2-9A-HJKMNP-Z]{4}-[2-9A-HJKMNP-Z]{4}-[2-9A-HJKMNP-Z]{4}$")


class SubmitReportTests(BaseAPITest):
    def test_valid_report_returns_201_and_receipt_code(self):  # FR-1.1, 1.6, 1.7, 1.10
        r = self.submit()
        self.assertEqual(r.status_code, 201, r.content)
        body = r.json()
        self.assertRegex(body["receipt_code"], CODE_PATTERN)
        self.assertEqual(body["status"], "pending")
        self.assertEqual(Report.objects.count(), 1)

    def test_only_hash_of_receipt_code_is_stored(self):  # FR-1.8
        code = self.submit().json()["receipt_code"]
        report = Report.objects.get()
        self.assertEqual(report.receipt_hash, hash_receipt_code(code))
        self.assertNotIn(code, report.receipt_hash)

    def test_submission_time_is_rounded_to_the_hour(self):  # FR-1.9
        self.submit()
        created = Report.objects.get().created_at
        self.assertEqual((created.minute, created.second, created.microsecond), (0, 0, 0))

    def test_report_text_is_encrypted_in_database(self):  # NFR-5
        self.submit()
        with connection.cursor() as c:
            c.execute("SELECT title, description FROM reports_report")
            raw_title, raw_description = c.fetchone()
        self.assertNotIn("land mutation", raw_title)
        self.assertNotIn("land mutation", raw_description)
        self.assertEqual(Report.objects.get().title, VALID_REPORT["title"])  # decrypts on read

    def test_district_is_case_insensitive_and_stored_canonically(self):  # FR-1.4
        self.assertEqual(self.submit(district="  dhaka ").status_code, 201)
        self.assertEqual(Report.objects.get().district, "Dhaka")

    def test_unknown_district_is_rejected(self):  # FR-1.4
        err = self.assertErrorShape(self.submit(district="Atlantis"), 400, "validation_error")
        self.assertIn("district", err["details"])

    def test_invalid_category_is_rejected(self):  # FR-1.3
        err = self.assertErrorShape(self.submit(category="gossip"), 400, "validation_error")
        self.assertIn("category", err["details"])

    def test_short_title_and_description_are_rejected(self):  # FR-1.2
        err = self.assertErrorShape(self.submit(title="Short", description="Too short"), 400, "validation_error")
        self.assertIn("title", err["details"])
        self.assertIn("description", err["details"])

    def test_missing_required_fields_are_listed(self):  # NFR-11
        r = self.client.post("/api/reports/", {}, format="json")
        err = self.assertErrorShape(r, 400, "validation_error")
        for field in ("category", "district", "title", "description"):
            self.assertIn(field, err["details"])

    def test_future_incident_date_is_rejected(self):  # FR-1.5
        tomorrow = (timezone.localdate() + datetime.timedelta(days=1)).isoformat()
        err = self.assertErrorShape(self.submit(incident_date=tomorrow), 400, "validation_error")
        self.assertIn("incident_date", err["details"])

    def test_very_old_incident_date_is_rejected(self):  # FR-1.5
        err = self.assertErrorShape(self.submit(incident_date="2015-01-01"), 400, "validation_error")
        self.assertIn("incident_date", err["details"])

    def test_near_identical_report_is_flagged_as_duplicate(self):  # FR-1.11
        self.submit()
        self.submit(description=VALID_REPORT["description"] + " Please check.")
        first, second = Report.objects.order_by("id")
        self.assertEqual(second.possible_duplicate_of_id, first.id)
        self.assertGreaterEqual(second.duplicate_score, 0.75)

    def test_different_report_is_not_flagged(self):  # FR-1.11
        self.submit()
        self.submit(title="Hospital charges for free tests",
                    description="The hospital lab charges 800 taka for blood tests that are listed as free for all patients.")
        self.assertIsNone(Report.objects.order_by("id").last().possible_duplicate_of)

    def test_too_many_submissions_are_rate_limited(self):  # NFR-4
        # Lower the limit to 2 per hour just for this test.
        with patch.object(ReportSubmitThrottle, "THROTTLE_RATES", {"report_submit": "2/hour"}):
            self.assertEqual(self.submit().status_code, 201)
            self.assertEqual(self.submit(title="Second report about fees").status_code, 201)
            self.assertErrorShape(self.submit(title="Third report about fees"), 429, "rate_limited")


class PhotoTests(BaseAPITest):
    def _jpeg_with_metadata(self):
        img = Image.new("RGB", (40, 30), "green")
        exif = Image.Exif()
        exif[0x010F] = "PhoneMaker"  # camera make
        exif[0x0110] = "Model X"  # camera model
        exif[0x0132] = "2026:11:01 14:32:10"  # exact date and time taken
        buf = io.BytesIO()
        img.save(buf, format="JPEG", exif=exif)
        buf.name = "IMG_1234_my_name.jpg"
        buf.seek(0)
        return buf

    def test_photo_metadata_is_removed_and_file_renamed(self):  # FR-1.12
        photo = self._jpeg_with_metadata()
        self.assertGreater(len(Image.open(photo).getexif()), 0)  # metadata is there before upload
        photo.seek(0)
        r = self.client.post("/api/reports/", {**VALID_REPORT, "photos": [photo]}, format="multipart")
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(r.json()["photos_received"], 1)
        att = Attachment.objects.get()
        self.assertNotIn("my_name", att.file.name)
        with att.file.open("rb") as f:
            self.assertEqual(len(Image.open(f).getexif()), 0)

    def test_non_image_file_is_rejected(self):  # FR-1.12
        fake = io.BytesIO(b"not an image at all")
        fake.name = "evil.jpg"
        r = self.client.post("/api/reports/", {**VALID_REPORT, "photos": [fake]}, format="multipart")
        err = self.assertErrorShape(r, 400, "validation_error")
        self.assertIn("photos", err["details"])
        self.assertEqual(Report.objects.count(), 0)

    def test_photos_are_only_downloadable_by_reviewers(self):  # FR-4.10
        photo = self._jpeg_with_metadata()
        self.client.post("/api/reports/", {**VALID_REPORT, "photos": [photo]}, format="multipart")
        url = f"/api/review/attachments/{Attachment.objects.get().id}/"
        self.assertErrorShape(self.client.get(url), 401, "not_authenticated")
        self.as_outsider()
        self.assertErrorShape(self.client.get(url), 403, "permission_denied")
        self.as_reviewer()
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "image/jpeg")

