"""
python manage.py seed_demo

Creates the demo reviewer account and a handful of realistic sample reports
in different states, so the API has something to show straight away.
Safe to run more than once.

If DJANGO_ADMIN_USERNAME and DJANGO_ADMIN_PASSWORD are set (for example on the
hosting server), it also creates or updates a superuser for the Django admin.
The password comes only from the environment, never from the code.
"""

import datetime
import os

from django.contrib.auth.models import Group, User
from django.core.management.base import BaseCommand
from django.utils import timezone

from reports import services
from reports.models import Report
from reports.permissions import REVIEWER_GROUP

DEMO_USER = "reviewer"
DEMO_PASSWORD = "review-demo-2026"

SAMPLES = [
    {
        "data": {
            "category": "bribery", "district": "Dhaka", "area": "Savar AC Land Office",
            "title": "Cash demanded for land mutation",
            "description": "An office assistant asked for 15,000 taka in cash to process a land mutation "
                           "that should cost only the official fee. No receipt was given.",
        },
        "review": {"decision": "verify", "note": "Consistent with two other reports.",
                   "public_summary": "Citizens report unofficial cash fees being demanded for land mutation at a Savar land office."},
    },
    {
        "data": {
            "category": "healthcare", "district": "Rangpur", "area": "Upazila Health Complex",
            "title": "Free medicine being sold to patients",
            "description": "Medicines that are supposed to be free at the government health complex are being "
                           "sold to patients from a shop right outside the gate by hospital staff.",
        },
        "review": {"decision": "verify", "note": "Photo evidence and date match.",
                   "public_summary": "Reports that free government medicines at a Rangpur upazila health complex are being sold to patients."},
    },
    {
        "data": {
            "category": "education", "district": "Cumilla",
            "title": "Stipend money not reaching students",
            "description": "Several students at a government primary school say their stipend has not been "
                           "paid for six months while records show it was disbursed.",
        },
        "review": None,
    },
    {
        "data": {
            "category": "misuse_of_funds", "district": "Khulna", "area": "Ward 12 road project",
            "title": "Road repaired on paper but not in reality",
            "description": "A road repair project in ward 12 was marked complete with full payment, but the road "
                           "is still broken and no work was done in the last year.",
        },
        "review": None,
    },
    {
        "data": {
            "category": "public_service", "district": "Sylhet",
            "title": "Everything is bad here",
            "description": "Everything is bad here and nothing works, the government should fix everything now.",
        },
        "review": {"decision": "reject", "note": "No specific office, place or incident described."},
    },
    {
        # Near-copy of the first sample, to show duplicate detection.
        "data": {
            "category": "bribery", "district": "Dhaka", "area": "Savar land office",
            "title": "Cash demanded for land mutation in Savar",
            "description": "The office assistant asked for 15,000 taka cash to process my land mutation, which "
                           "should only cost the official fee. No receipt was given to me.",
        },
        "review": None,
    },
]


class Command(BaseCommand):
    help = "Create the demo reviewer and sample reports."

    def handle(self, *args, **options):
        group, _ = Group.objects.get_or_create(name=REVIEWER_GROUP)
        user, created = User.objects.get_or_create(username=DEMO_USER)
        if created:
            user.set_password(DEMO_PASSWORD)
            user.save()
        user.groups.add(group)
        self.stdout.write(f"Reviewer account: {DEMO_USER} / {DEMO_PASSWORD}")

        admin_name = os.environ.get("DJANGO_ADMIN_USERNAME")
        admin_password = os.environ.get("DJANGO_ADMIN_PASSWORD")
        if admin_name and admin_password:
            admin, _ = User.objects.get_or_create(username=admin_name)
            admin.is_staff = True
            admin.is_superuser = True
            admin.set_password(admin_password)
            admin.save()
            self.stdout.write(f"Admin account ready: {admin_name}")

        if Report.objects.exists():
            self.stdout.write("Sample reports already exist, skipping.")
            return

        today = timezone.localdate()
        for i, sample in enumerate(SAMPLES):
            data = dict(sample["data"], incident_date=today - datetime.timedelta(days=10 - i))
            report, code = services.create_report(data)
            if sample["review"]:
                report = services.review_report(report.id, user, sample["review"])
            self.stdout.write(f"  {report.status:9} {code}  {data['title']}")
        self.stdout.write(self.style.SUCCESS(f"Created {len(SAMPLES)} sample reports."))
