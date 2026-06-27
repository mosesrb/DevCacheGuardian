"""
scoring.py — Health score computation (extracted from db.py, SRP fix F15).

This module owns the business logic for turning a list of CacheItems into a
0-100 health score + grade.  It has no database dependency and can be unit-
tested without touching SQLite.
"""
from __future__ import annotations

from app.models import CacheItem, RiskLevel
from app.utils import fmt_bytes


# Weight constants — tweak here to adjust scoring sensitivity
_SAFE_DEDUCT_PER_GB   = 4.0   # max 40 pts
_REVIEW_DEDUCT_PER_GB = 1.0   # max 20 pts
_MAX_SAFE_DEDUCT      = 40
_MAX_REVIEW_DEDUCT    = 20


def get_health_score(items: list[CacheItem]) -> dict:
    """
    Compute a 0-100 health score and letter grade from scan results.

    Returns a dict:
        {
            "score":     int (0-100),
            "grade":     str ("A"-"F"),
            "breakdown": {
                "safe_reclaimable": str (human-readable),
                "needs_review":     str,
                "total_found":      str,
            }
        }

    Pure function — no I/O, no DB calls. Safe to call from any thread.
    """
    if not items:
        return {"score": 100, "grade": "A", "breakdown": {}}

    total  = sum(i.size_bytes for i in items)
    safe   = sum(i.size_bytes for i in items if i.risk_level == RiskLevel.SAFE)
    review = sum(i.size_bytes for i in items if i.risk_level == RiskLevel.REVIEW)

    safe_gb   = safe   / 1024 ** 3
    review_gb = review / 1024 ** 3

    deductions = (
        min(_MAX_SAFE_DEDUCT,   safe_gb   * _SAFE_DEDUCT_PER_GB) +
        min(_MAX_REVIEW_DEDUCT, review_gb * _REVIEW_DEDUCT_PER_GB)
    )
    score = max(0, round(100 - deductions))

    if   score >= 90: grade = "A"
    elif score >= 75: grade = "B"
    elif score >= 60: grade = "C"
    elif score >= 40: grade = "D"
    else:             grade = "F"

    return {
        "score": score,
        "grade": grade,
        "breakdown": {
            "safe_reclaimable": fmt_bytes(safe),
            "needs_review":     fmt_bytes(review),
            "total_found":      fmt_bytes(total),
        },
    }
