"""SmartRecruiters public Postings API adapter.

Docs: https://developers.smartrecruiters.com/docs/endpoints
No auth required — GET https://api.smartrecruiters.com/v1/companies/{companyIdentifier}/postings
Caveat (per SmartRecruiters' own docs): this public feed is tier-dependent —
not every company on SmartRecruiters has it enabled on their plan. A
company that doesn't will just return an empty/error result here, same as
any other adapter hitting a slug that doesn't exist — no special handling
needed, it fails gracefully like the others.
"""
from __future__ import annotations

import httpx

from app.ats_adapters.base import RawPosting

BASE_URL = "https://api.smartrecruiters.com/v1/companies/{company_id}/postings"


class SmartRecruitersAdapter:
    ats_type = "smartrecruiters"

    def list_postings(self, board_token: str) -> list[RawPosting]:
        url = BASE_URL.format(company_id=board_token)
        resp = httpx.get(url, params={"limit": 100}, timeout=20)
        resp.raise_for_status()
        content = resp.json().get("content", [])

        postings: list[RawPosting] = []
        for job in content:
            location = job.get("location", {}) or {}
            location_str = ", ".join(
                part for part in [location.get("city"), location.get("region"), location.get("country")] if part
            )
            postings.append(
                RawPosting(
                    external_id=str(job.get("id", "")),
                    title=job.get("name", ""),
                    location=location_str or None,
                    remote=bool(location.get("remote")),
                    url=job.get("applyUrl") or job.get("postingUrl", ""),
                    # List endpoint doesn't include full description — SmartRecruiters'
                    # own docs note you need the per-posting detail call ('ref') for
                    # that. Left blank here rather than firing N extra requests per
                    # discovery run; the matcher still has title + location to work
                    # with, same tradeoff Workday's list endpoint makes.
                    description_raw="",
                    posted_at=job.get("releasedDate"),
                )
            )
        return postings
