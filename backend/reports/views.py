from django.contrib.auth import authenticate
from django.db.models import Count
from django.http import FileResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import (
    OpenApiExample,
    OpenApiParameter,
    OpenApiResponse,
    extend_schema,
    inline_serializer,
)
from rest_framework import exceptions, generics, serializers, status
from rest_framework.authtoken.models import Token
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from . import services
from .constants import DISTRICTS, Category, Status
from .models import Attachment, Report
from .permissions import IsReviewer, is_reviewer
from .security import hash_receipt_code, normalize_receipt_code
from .serializers import (
    MAX_PHOTOS,
    LoginResponseSerializer,
    LoginSerializer,
    MetaSerializer,
    PublicReportSerializer,
    ReportCreatedSerializer,
    ReportCreateSerializer,
    ReportTrackSerializer,
    ReviewDecisionSerializer,
    ReviewerReportDetailSerializer,
    ReviewerReportListSerializer,
    StatsSerializer,
)
from .throttles import ReportSubmitThrottle, ReportTrackThrottle

ERROR = inline_serializer(
    "Error",
    fields={
        "error": inline_serializer(
            "ErrorBody",
            fields={
                "status": serializers.IntegerField(),
                "code": serializers.CharField(),
                "message": serializers.CharField(),
                "details": serializers.DictField(required=False),
            },
        )
    },
)


def err(description):
    return OpenApiResponse(ERROR, description=description)


# ---------------------------------------------------------------------------
# Reporting (anonymous)
# ---------------------------------------------------------------------------


class ReportCreateView(APIView):
    """Core feature: submit an anonymous report."""

    authentication_classes = []  # never tie a report to an account
    permission_classes = [AllowAny]
    throttle_classes = [ReportSubmitThrottle]
    parser_classes = [JSONParser, MultiPartParser, FormParser]

    @extend_schema(
        tags=["Reporting"],
        summary="Submit an anonymous report",
        description=(
            "No login, no IP address stored. Returns a one-time **receipt code**; "
            "only its keyed hash is kept, so it cannot be recovered if lost.\n\n"
            "Send JSON, or `multipart/form-data` to attach up to 3 photos "
            "(EXIF/GPS metadata is stripped)."
        ),
        request={
            "application/json": ReportCreateSerializer,
            "multipart/form-data": ReportCreateSerializer,
        },
        responses={
            201: ReportCreatedSerializer,
            400: err("Validation failed"),
            429: err("Too many submissions"),
        },
        examples=[
            OpenApiExample(
                "Bribe at a land office",
                request_only=True,
                value={
                    "category": "bribery",
                    "district": "Dhaka",
                    "area": "Savar AC Land Office",
                    "title": "Extra fee demanded for land mutation",
                    "description": (
                        "An office assistant asked for 15,000 taka in cash to process a land "
                        "mutation that should cost the official fee only. No receipt was given."
                    ),
                    "incident_date": "2026-10-20",
                },
            )
        ],
    )
    def post(self, request):
        serializer = ReportCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        photo_count = len(serializer.validated_data.get("photos", []))
        report, code = services.create_report(dict(serializer.validated_data))
        body = {
            "receipt_code": code,
            "status": report.status,
            "submitted_on": timezone.localtime(report.created_at).date(),
            "photos_received": photo_count,
            "message": "Report received. Save your receipt code now: it is shown only once.",
        }
        return Response(ReportCreatedSerializer(body).data, status=status.HTTP_201_CREATED)


class ReportTrackView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = [ReportTrackThrottle]

    @extend_schema(
        tags=["Reporting"],
        summary="Track a report with its receipt code",
        description="Dashes and lowercase are fine: `nb7k3mq9tx4hpa` works too.",
        responses={200: ReportTrackSerializer, 404: err("No report with this code"), 429: err("Too many attempts")},
    )
    def get(self, request, receipt_code):
        normalized = normalize_receipt_code(receipt_code)
        if not normalized:
            raise exceptions.NotFound("No report found for this receipt code.")
        report = Report.objects.filter(receipt_hash=hash_receipt_code(normalized)).first()
        if not report:
            raise exceptions.NotFound("No report found for this receipt code.")
        return Response(ReportTrackSerializer(report).data)


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------


class LoginView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = [ReportTrackThrottle]  # also slows password guessing

    def get_authenticate_header(self, request):
        # Without this, DRF turns 401 into 403 for views with no authentication
        # class. A wrong password must be 401 (FR-3.3).
        return "Token"

    @extend_schema(
        tags=["Auth"],
        summary="Reviewer login",
        description="Demo account: `reviewer` / `review-demo-2026`. Use the token as `Token <token>` in **Authorize**.",
        request=LoginSerializer,
        responses={
            200: LoginResponseSerializer,
            400: err("Missing fields"),
            401: err("Wrong username or password"),
            403: err("Account exists but is not in the reviewers group"),
            429: err("Too many login attempts"),
        },
    )
    def post(self, request):
        s = LoginSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        user = authenticate(username=s.validated_data["username"], password=s.validated_data["password"])
        if not user:
            raise exceptions.AuthenticationFailed("Incorrect username or password.")
        if not is_reviewer(user):
            raise exceptions.PermissionDenied("This account is not a reviewer.")
        token, _ = Token.objects.get_or_create(user=user)
        return Response({"token": token.key, "username": user.username})


# ---------------------------------------------------------------------------
# Reviewer
# ---------------------------------------------------------------------------

REVIEW_FILTERS = [
    OpenApiParameter("status", str, enum=[s for s, _ in Status.choices]),
    OpenApiParameter("category", str, enum=[c for c, _ in Category.choices]),
    OpenApiParameter("district", str),
    OpenApiParameter("duplicates_only", bool, description="Only reports flagged as possible duplicates"),
]


class ReviewerReportListView(generics.ListAPIView):
    permission_classes = [IsReviewer]
    serializer_class = ReviewerReportListSerializer

    @extend_schema(
        tags=["Reviewer"],
        summary="List reports for review",
        parameters=REVIEW_FILTERS,
        responses={200: ReviewerReportListSerializer(many=True), 401: err("Not logged in"), 403: err("Not a reviewer")},
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    def get_queryset(self):
        qs = Report.objects.prefetch_related("attachments")
        p = self.request.query_params
        if p.get("status"):
            if p["status"] not in Status.values:
                raise exceptions.ValidationError({"status": [f"Must be one of {Status.values}."]})
            qs = qs.filter(status=p["status"])
        if p.get("category"):
            if p["category"] not in Category.values:
                raise exceptions.ValidationError({"category": [f"Must be one of {Category.values}."]})
            qs = qs.filter(category=p["category"])
        if p.get("district"):
            qs = qs.filter(district__iexact=p["district"])
        if p.get("duplicates_only", "").lower() in ("1", "true", "yes"):
            qs = qs.filter(possible_duplicate_of__isnull=False)
        return qs


class ReviewerReportDetailView(APIView):
    permission_classes = [IsReviewer]

    @extend_schema(
        tags=["Reviewer"],
        summary="Get one report with photos and review history",
        responses={200: ReviewerReportDetailSerializer, 401: err("Not logged in"), 403: err("Not a reviewer"), 404: err("Not found")},
    )
    def get(self, request, pk):
        report = get_object_or_404(Report, pk=pk)
        return Response(ReviewerReportDetailSerializer(report, context={"request": request}).data)

    @extend_schema(
        tags=["Reviewer"],
        summary="Verify or reject a report",
        description="Only `pending` reports can be reviewed. Every decision is saved to the audit trail.",
        request=ReviewDecisionSerializer,
        responses={
            200: ReviewerReportDetailSerializer,
            400: err("Validation failed"),
            401: err("Not logged in"),
            403: err("Not a reviewer"),
            404: err("Not found"),
            409: err("Report was already reviewed"),
        },
        examples=[
            OpenApiExample(
                "Verify",
                request_only=True,
                value={
                    "decision": "verify",
                    "note": "Matches two other reports from the same office.",
                    "public_summary": "Multiple citizens report unofficial cash fees for land mutation at a Savar land office.",
                },
            ),
            OpenApiExample(
                "Reject",
                request_only=True,
                value={"decision": "reject", "note": "No specific office or incident described."},
            ),
        ],
    )
    def patch(self, request, pk):
        get_object_or_404(Report, pk=pk)
        s = ReviewDecisionSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        report = services.review_report(pk, request.user, s.validated_data)
        return Response(ReviewerReportDetailSerializer(report, context={"request": request}).data)


class AttachmentDownloadView(APIView):
    """Evidence photos are only served to reviewers, never from a public URL."""

    permission_classes = [IsReviewer]

    @extend_schema(
        tags=["Reviewer"],
        summary="Download an evidence photo",
        responses={(200, "image/*"): OpenApiTypes.BINARY, 401: err("Not logged in"), 403: err("Not a reviewer"), 404: err("Not found")},
    )
    def get(self, request, pk):
        att = get_object_or_404(Attachment, pk=pk)
        return FileResponse(att.file.open("rb"), content_type=att.content_type)


# ---------------------------------------------------------------------------
# Public
# ---------------------------------------------------------------------------


class PublicReportListView(generics.ListAPIView):
    authentication_classes = []
    permission_classes = [AllowAny]
    serializer_class = PublicReportSerializer

    @extend_schema(
        tags=["Public"],
        summary="Verified reports (public summaries only)",
        parameters=[
            OpenApiParameter("category", str, enum=[c for c, _ in Category.choices]),
            OpenApiParameter("district", str),
        ],
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    def get_queryset(self):
        qs = Report.objects.filter(status=Status.VERIFIED).order_by("-reviewed_at")
        p = self.request.query_params
        if p.get("category"):
            qs = qs.filter(category=p["category"])
        if p.get("district"):
            qs = qs.filter(district__iexact=p["district"])
        return qs


class PublicStatsView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    @extend_schema(tags=["Public"], summary="Report statistics", responses={200: StatsSerializer})
    def get(self, request):
        by_status = dict(Report.objects.values_list("status").annotate(c=Count("id")))
        verified = Report.objects.filter(status=Status.VERIFIED)
        labels = dict(Category.choices)
        by_cat = [
            {"key": row["category"], "label": labels.get(row["category"], row["category"]), "count": row["c"]}
            for row in verified.values("category").annotate(c=Count("id")).order_by("-c")
        ]
        by_dist = [
            {"key": row["district"], "label": row["district"], "count": row["c"]}
            for row in verified.values("district").annotate(c=Count("id")).order_by("-c")[:10]
        ]
        data = {
            "total_received": sum(by_status.values()),
            "pending": by_status.get(Status.PENDING, 0),
            "verified": by_status.get(Status.VERIFIED, 0),
            "rejected": by_status.get(Status.REJECTED, 0),
            "verified_by_category": by_cat,
            "verified_by_district": by_dist,
        }
        return Response(StatsSerializer(data).data)


class MetaView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    @extend_schema(tags=["Public"], summary="Valid categories, districts and statuses", responses={200: MetaSerializer})
    def get(self, request):
        return Response(
            {
                "categories": [{"value": v, "label": l} for v, l in Category.choices],
                "districts": DISTRICTS,
                "statuses": [{"value": v, "label": l} for v, l in Status.choices],
                "max_photos": MAX_PHOTOS,
            }
        )


class HealthView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    @extend_schema(
        tags=["Public"],
        summary="Health check",
        responses={200: inline_serializer("Health", {"status": serializers.CharField()})},
    )
    def get(self, request):
        return Response({"status": "ok"})
