"""Applies user-configured filters to postings before they're even scored.
This runs as a hard pre-filter — a posting that fails here never reaches
the matcher, never costs an LLM call, and gets a clear reason logged so
'why didn't I see this job' has an answer.

Filters are read from config.yaml's `filters:` block (see config.example.yaml).
All filters are optional — an empty/missing filters block means "no extra
constraints," matching the pre-filter-system behavior.
"""
from __future__ import annotations

from datetime import datetime, timezone

from app.db.models import Posting


def _tokenize_lower(text: str) -> str:
    return (text or "").lower()


def passes_filters(posting: Posting, cfg: dict) -> tuple[bool, str]:
    """Returns (passes, reason). reason explains a failure, or is empty on pass."""
    filters = cfg.get("filters", {}) or {}

    # --- Date posted ---
    max_days = filters.get("max_days_since_posted")
    if max_days is not None and posting.posted_at is not None:
        posted_at = posting.posted_at
        if posted_at.tzinfo is None:
            posted_at = posted_at.replace(tzinfo=timezone.utc)
        age_days = (datetime.now(timezone.utc) - posted_at).days
        if age_days > max_days:
            return False, f"posted {age_days}d ago, older than max_days_since_posted={max_days}"
    # Note: if posted_at is None (the ATS didn't give us a usable date),
    # this filter is skipped rather than excluding the posting — an
    # unknown age shouldn't silently hide a job that might be a great fit.

    # --- Remote only ---
    if filters.get("remote_only") and not posting.remote:
        return False, "remote_only is set, posting isn't flagged remote"

    # --- Exclude keywords (title or description) ---
    exclude_keywords = filters.get("exclude_keywords", []) or []
    haystack = _tokenize_lower(posting.title + " " + posting.description_raw)
    for kw in exclude_keywords:
        if kw.lower() in haystack:
            return False, f"matched exclude_keywords: {kw!r}"

    # --- Require keywords (at least one must appear, if the list is non-empty) ---
    require_keywords = filters.get("require_keywords", []) or []
    if require_keywords:
        if not any(kw.lower() in haystack for kw in require_keywords):
            return False, f"matched none of require_keywords: {require_keywords}"

    # --- Relocation / location hard-exclude ---
    # Reuses the same locations_excluded logic already in the matcher so
    # there's exactly one source of truth for "what counts as out of
    # scope geographically" — see app/services/matcher.py location_score.
    locations_excluded = [loc.lower() for loc in cfg.get("locations_excluded", [])]
    if posting.location:
        loc_lower = posting.location.lower()
        if any(bad in loc_lower for bad in locations_excluded):
            return False, f"location {posting.location!r} is in locations_excluded"

    return True, ""


def filter_new_postings() -> dict[str, int]:
    """Runs passes_filters() over every posting still in 'new' status.
    Postings that fail get status='filtered_out' with the reason stored in
    a note; postings that pass move to 'scored' pending status is what
    match() then does its heuristic/LLM pass on. Returns counts."""
    from sqlmodel import select
    from app.core.config import load_config
    from app.db.session import get_session

    cfg = load_config()
    kept = 0
    filtered = 0

    with get_session() as session:
        postings = session.exec(select(Posting).where(Posting.status == "new")).all()
        for posting in postings:
            ok, reason = passes_filters(posting, cfg)
            if ok:
                kept += 1
                # status stays "new" — match() will pick these up as before
            else:
                posting.status = "filtered_out"
                posting.filter_reason = reason
                session.add(posting)
                filtered += 1
        session.commit()

    return {"kept": kept, "filtered": filtered}
