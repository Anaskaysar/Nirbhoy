"""
Flag reports that look like copies of an earlier one, so reviewers can spot
spam or the same incident reported many times. Nothing is auto-rejected:
a human always decides.
"""

import datetime
import re
from difflib import SequenceMatcher

from django.utils import timezone

DUPLICATE_THRESHOLD = 0.75
LOOKBACK_DAYS = 30
MAX_CANDIDATES = 200


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s]", " ", text.lower())).strip()


def similarity(a: str, b: str) -> float:
    a, b = _normalize(a), _normalize(b)
    if not a or not b:
        return 0.0
    words_a, words_b = set(a.split()), set(b.split())
    jaccard = len(words_a & words_b) / len(words_a | words_b)
    sequence = SequenceMatcher(None, a, b).ratio()
    return round(max(jaccard, sequence), 3)


def find_possible_duplicate(category, district, title, description):
    """
    Compare against recent reports in the same district and category.
    Because report text is encrypted in the database we cannot search it with
    SQL, so we decrypt a small, bounded set of candidates in memory.
    Returns (report, score) or (None, None).
    """
    from .models import Report

    since = timezone.now() - datetime.timedelta(days=LOOKBACK_DAYS)
    candidates = Report.objects.filter(
        category=category, district=district, created_at__gte=since
    ).order_by("-created_at")[:MAX_CANDIDATES]

    new_text = f"{title} {description}"
    best, best_score = None, 0.0
    for other in candidates:
        score = similarity(new_text, f"{other.title} {other.description}")
        if score > best_score:
            best, best_score = other, score
    if best and best_score >= DUPLICATE_THRESHOLD:
        return best, best_score
    return None, None
