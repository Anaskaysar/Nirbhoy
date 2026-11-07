import uuid

from django.conf import settings
from django.db import models

from .constants import Category, Decision, Status
from .security import EncryptedTextField


class Report(models.Model):
    """
    One anonymous report. Note what is NOT here: no user, no IP address,
    no device info, no receipt code in plain text.
    """

    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    category = models.CharField(max_length=32, choices=Category.choices, db_index=True)
    district = models.CharField(max_length=40, db_index=True)
    area = models.CharField(max_length=120, blank=True)
    title = EncryptedTextField()
    description = EncryptedTextField()
    incident_date = models.DateField(null=True, blank=True)

    status = models.CharField(
        max_length=16, choices=Status.choices, default=Status.PENDING, db_index=True
    )
    receipt_hash = models.CharField(max_length=64, unique=True)

    # Filled by the system when a very similar report already exists.
    possible_duplicate_of = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.SET_NULL, related_name="similar_reports"
    )
    duplicate_score = models.FloatField(null=True, blank=True)

    # Written by a reviewer. Only this text is published, never the raw report.
    public_summary = models.TextField(blank=True)
    reviewer_message = models.CharField(max_length=300, blank=True)

    created_at = models.DateTimeField()
    reviewed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        # Times are rounded to the hour, so id breaks ties (newest first).
        ordering = ["-created_at", "-id"]

    def __str__(self):
        return f"{self.get_category_display()} in {self.district} ({self.status})"


def attachment_path(instance, filename):
    return f"evidence/{instance.report.public_id}/{filename}"


class Attachment(models.Model):
    report = models.ForeignKey(Report, on_delete=models.CASCADE, related_name="attachments")
    file = models.FileField(upload_to=attachment_path)
    content_type = models.CharField(max_length=40)
    size_bytes = models.PositiveIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)


class ReviewAction(models.Model):
    """Audit trail: who decided what, and why. Reviewers are accountable too."""

    report = models.ForeignKey(Report, on_delete=models.CASCADE, related_name="review_actions")
    reviewer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    decision = models.CharField(max_length=16, choices=Decision.choices)
    note = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
