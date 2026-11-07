import datetime

from django.utils import timezone
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from .constants import DISTRICTS, Category, Decision
from .models import Attachment, Report, ReviewAction
from .security import PhotoError, clean_photo

MAX_PHOTOS = 3

# ---------------------------------------------------------------------------
# Citizen: submit a report
# ---------------------------------------------------------------------------


class ReportCreateSerializer(serializers.Serializer):
    category = serializers.ChoiceField(choices=Category.choices)
    district = serializers.CharField(max_length=40, help_text="One of the 64 districts, e.g. 'Dhaka'.")
    area = serializers.CharField(
        max_length=120, required=False, allow_blank=True,
        help_text="Upazila, thana or office name (optional). Avoid personal names.",
    )
    title = serializers.CharField(min_length=10, max_length=120)
    description = serializers.CharField(min_length=30, max_length=3000)
    incident_date = serializers.DateField(required=False, allow_null=True)
    photos = serializers.ListField(
        child=serializers.FileField(),
        required=False,
        max_length=MAX_PHOTOS,
        help_text="Up to 3 images (JPEG/PNG/WEBP, 5 MB each). Location data is removed.",
    )

    def validate_district(self, value):
        match = next((d for d in DISTRICTS if d.lower() == value.strip().lower()), None)
        if not match:
            raise serializers.ValidationError(
                "Unknown district. Use GET /api/meta/ for the list of valid districts."
            )
        return match

    def validate_incident_date(self, value):
        if value is None:
            return value
        today = timezone.localdate()
        if value > today:
            raise serializers.ValidationError("Incident date cannot be in the future.")
        if value < today - datetime.timedelta(days=5 * 365):
            raise serializers.ValidationError("Incident date must be within the last 5 years.")
        return value

    def validate_photos(self, files):
        cleaned = []
        for i, f in enumerate(files, start=1):
            try:
                cleaned.append(clean_photo(f))
            except PhotoError as e:
                raise serializers.ValidationError(f"Photo {i}: {e}")
        return cleaned

    def validate(self, attrs):
        for field in ("title", "description", "area"):
            if field in attrs and isinstance(attrs[field], str):
                attrs[field] = attrs[field].strip()
        return attrs


class ReportCreatedSerializer(serializers.Serializer):
    receipt_code = serializers.CharField(help_text="Shown only once. The reporter must save it.")
    status = serializers.CharField()
    submitted_on = serializers.DateField()
    photos_received = serializers.IntegerField()
    message = serializers.CharField()


# ---------------------------------------------------------------------------
# Citizen: track a report
# ---------------------------------------------------------------------------


class ReportTrackSerializer(serializers.ModelSerializer):
    category = serializers.CharField(source="get_category_display")
    status_label = serializers.CharField(source="get_status_display")
    submitted_on = serializers.SerializerMethodField()
    reviewed_on = serializers.SerializerMethodField()

    class Meta:
        model = Report
        fields = ["status", "status_label", "category", "district", "submitted_on", "reviewed_on", "reviewer_message"]

    @extend_schema_field(serializers.DateField())
    def get_submitted_on(self, obj):
        return timezone.localtime(obj.created_at).date()

    @extend_schema_field(serializers.DateField(allow_null=True))
    def get_reviewed_on(self, obj):
        return timezone.localtime(obj.reviewed_at).date() if obj.reviewed_at else None


# ---------------------------------------------------------------------------
# Reviewer
# ---------------------------------------------------------------------------


class AttachmentSerializer(serializers.ModelSerializer):
    url = serializers.SerializerMethodField()

    class Meta:
        model = Attachment
        fields = ["id", "content_type", "size_bytes", "url"]

    @extend_schema_field(serializers.URLField())
    def get_url(self, obj):
        request = self.context.get("request")
        path = f"/api/review/attachments/{obj.id}/"
        return request.build_absolute_uri(path) if request else path


class ReviewActionSerializer(serializers.ModelSerializer):
    reviewer = serializers.CharField(source="reviewer.username")

    class Meta:
        model = ReviewAction
        fields = ["decision", "note", "reviewer", "created_at"]


class ReviewerReportListSerializer(serializers.ModelSerializer):
    category_label = serializers.CharField(source="get_category_display")
    photo_count = serializers.IntegerField(source="attachments.count")
    possible_duplicate_of = serializers.IntegerField(source="possible_duplicate_of_id", allow_null=True)

    class Meta:
        model = Report
        fields = [
            "id", "category", "category_label", "district", "area", "title", "status",
            "incident_date", "created_at", "photo_count", "possible_duplicate_of", "duplicate_score",
        ]


class ReviewerReportDetailSerializer(ReviewerReportListSerializer):
    attachments = AttachmentSerializer(many=True)
    review_history = ReviewActionSerializer(source="review_actions", many=True)

    class Meta(ReviewerReportListSerializer.Meta):
        fields = ReviewerReportListSerializer.Meta.fields + [
            "description", "public_summary", "reviewer_message", "reviewed_at",
            "attachments", "review_history",
        ]


class ReviewDecisionSerializer(serializers.Serializer):
    decision = serializers.ChoiceField(choices=Decision.choices)
    note = serializers.CharField(
        max_length=1000, required=False, allow_blank=True,
        help_text="Internal note for the audit trail (not shown publicly).",
    )
    public_summary = serializers.CharField(
        max_length=600, required=False, allow_blank=True,
        help_text="Required when verifying. This is the only text that gets published.",
    )
    reviewer_message = serializers.CharField(
        max_length=300, required=False, allow_blank=True,
        help_text="Short message the reporter sees when tracking with their receipt code.",
    )

    def validate(self, attrs):
        if attrs["decision"] == Decision.VERIFY and len(attrs.get("public_summary", "").strip()) < 20:
            raise serializers.ValidationError(
                {"public_summary": "A public summary of at least 20 characters is required to verify a report."}
            )
        if attrs["decision"] == Decision.REJECT and not attrs.get("note", "").strip():
            raise serializers.ValidationError(
                {"note": "Please give a reason when rejecting a report."}
            )
        return attrs


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField(style={"input_type": "password"}, write_only=True)


class LoginResponseSerializer(serializers.Serializer):
    token = serializers.CharField()
    username = serializers.CharField()


# ---------------------------------------------------------------------------
# Public
# ---------------------------------------------------------------------------


class PublicReportSerializer(serializers.ModelSerializer):
    id = serializers.UUIDField(source="public_id")
    category_label = serializers.CharField(source="get_category_display")
    verified_on = serializers.SerializerMethodField()

    class Meta:
        model = Report
        fields = ["id", "category", "category_label", "district", "public_summary", "verified_on"]

    @extend_schema_field(serializers.DateField())
    def get_verified_on(self, obj):
        return timezone.localtime(obj.reviewed_at).date() if obj.reviewed_at else None


class CountItemSerializer(serializers.Serializer):
    key = serializers.CharField()
    label = serializers.CharField()
    count = serializers.IntegerField()


class StatsSerializer(serializers.Serializer):
    total_received = serializers.IntegerField()
    pending = serializers.IntegerField()
    verified = serializers.IntegerField()
    rejected = serializers.IntegerField()
    verified_by_category = CountItemSerializer(many=True)
    verified_by_district = CountItemSerializer(many=True)


class ChoiceSerializer(serializers.Serializer):
    value = serializers.CharField()
    label = serializers.CharField()


class MetaSerializer(serializers.Serializer):
    categories = ChoiceSerializer(many=True)
    districts = serializers.ListField(child=serializers.CharField())
    statuses = ChoiceSerializer(many=True)
    max_photos = serializers.IntegerField()

