"""Auto-detects which ATS a company uses, so companies can be added by name
instead of manually looking up ats_type + board_token.

Tries common slug variants against each adapter's real endpoint. Whichever
one returns a non-empty job list wins. This makes real network calls (to
the same public APIs the adapters already use) — no scraping, no guessing
that touches anything but each platform's documented/observed public feed.
"""
from __future__ import annotations

import re

from app.ats_adapters.ashby import AshbyAdapter
from app.ats_adapters.greenhouse import GreenhouseAdapter
from app.ats_adapters.lever import LeverAdapter
from app.ats_adapters.smartrecruiters import SmartRecruitersAdapter

# Workday deliberately excluded: its "token" is a tenant/wdN/site triple
# that can't be guessed from a company name the way a Greenhouse/Lever/
# Ashby/SmartRecruiters slug can — see CLAUDE.md §5. Add Workday companies
# manually with their real careers URL.
ADAPTERS = {
    "greenhouse": GreenhouseAdapter(),
    "lever": LeverAdapter(),
    "ashby": AshbyAdapter(),
    "smartrecruiters": SmartRecruitersAdapter(),
}


def _slug_guesses(name: str) -> list[str]:
    base = re.sub(r"[^a-z0-9]", "", name.lower())
    spaced = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    guesses = [base, spaced]
    # common suffix trims: "Example Inc" / "Example Co" / "Example AI"
    for suffix in (" inc", " co", " corp", " ai", " labs", " technologies", " technology"):
        if name.lower().endswith(suffix):
            trimmed = name[: -len(suffix)]
            guesses.append(re.sub(r"[^a-z0-9]", "", trimmed.lower()))
    seen = []
    for g in guesses:
        if g and g not in seen:
            seen.append(g)
    return seen


def resolve_company(name: str, extra_slug_guesses: list[str] | None = None) -> dict | None:
    """Try to find which ATS a company uses by name. Returns
    {"ats_type": ..., "board_token": ..., "posting_count": ...} or None."""
    guesses = _slug_guesses(name) + (extra_slug_guesses or [])

    for slug in guesses:
        for ats_type, adapter in ADAPTERS.items():
            try:
                postings = adapter.list_postings(slug)
            except Exception:  # noqa: BLE001 — 404s, network errors, bad slug: just try next
                continue
            if postings:
                return {"ats_type": ats_type, "board_token": slug, "posting_count": len(postings)}

    return None
