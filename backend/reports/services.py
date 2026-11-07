"""
Business logic lives here, not in views, so it can be tested and reused
(for example by a future WhatsApp bot or SMS gateway).
"""

from django.db import IntegrityError, transaction
from django.utils import timezone

from .constants import Decision, Status
from .duplicates import find_possible_duplicate
from .exceptions import Conflict
from .models import Attachment, Report, ReviewAction
from .security import generate_receipt_code, hash_receipt_code


def _coarse_now():
    """
    Store submission time rounded down to the hour. Exact timestamps can be
    matched against phone or network records to identify a reporter.
    """
    return timezone.now().replace(minute=0, second=0, microsecond=0)


@transaction.atomic
def create_report(data: dict) -> tuple[Report, str]:
    """Save a new report and return it together with the one-time receipt code."""
    photos = data.pop("photos", [])

    duplicate, score = find_possible_duplicate(
        data["category"], data["district"], data["title"], data["description"]
    )

    # Receipt codes are random; retry in the (astronomically rare) case of a clash.
    for _ in range(5):
        code = generate_receipt_code()
        try:
            with transaction.atomic():
                report = Report.objects.create(
                    **data,
                    receipt_hash=hash_receipt_code(code),
                    created_at=_coarse_now(),
                    possible_duplicate_of=duplicate,
                    duplicate_score=score,
                )
            break
        except IntegrityError:
            continue
    else:
        raise RuntimeError("Could not generate a unique receipt code.")

    for clean_file, _fmt in photos:
        Attachment.objects.create(
            report=report,
            file=clean_file,
            content_type=clean_file.content_type,
            size_bytes=clean_file.size,
        )
    return report, code


@transaction.atomic
def review_report(report_id: int, reviewer, data: dict) -> Report:
    # Lock the row so two reviewers cannot decide the same report at once.
    report = Report.objects.select_for_update().get(pk=report_id)
    if report.status != Status.PENDING:
        raise Conflict(
            f"This report was already {report.status}. Only pending reports can be reviewed."
        )

    decision = data["decision"]
    report.status = Status.VERIFIED if decision == Decision.VERIFY else Status.REJECTED
    report.reviewed_at = timezone.now()
    report.reviewer_message = data.get("reviewer_message", "").strip() or (
        "Thank you. Your report was verified and a summary has been published."
        if decision == Decision.VERIFY
        else "Thank you. We could not verify this report."
    )
    if decision == Decision.VERIFY:
        report.public_summary = data["public_summary"].strip()
    report.save()

    ReviewAction.objects.create(
        report=report, reviewer=reviewer, decision=decision, note=data.get("note", "").strip()
    )
    return report
