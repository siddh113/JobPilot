"""Greenhouse public job-board API adapter.

Docs: https://developers.greenhouse.io/job-board.html
No auth required — this endpoint is Greenhouse's official public feed,
meant for embedding job listings on company sites.
"""
from __future__ import annotations

import httpx

from app.ats_adapters.base import RawPosting

BASE_URL = "https://boards-api.greenhouse.io/v1/boards/{token}/jobs"


class GreenhouseAdapter:
    ats_type = "greenhouse"

    def list_postings(self, board_token: str) -> list[RawPosting]:
        url = BASE_URL.format(token=board_token)
        resp = httpx.get(url, params={"content": "true"}, timeout=20)
        resp.raise_for_status()
        jobs = resp.json().get("jobs", [])

        postings: list[RawPosting] = []
        for job in jobs:
            location = (job.get("location") or {}).get("name")
            postings.append(
                RawPosting(
                    external_id=str(job["id"]),
                    title=job.get("title", ""),
                    location=location,
                    remote=bool(location and "remote" in location.lower()),
                    url=job.get("absolute_url", ""),
                    description_raw=job.get("content", "") or "",
                    # Greenhouse's list endpoint gives "last updated", not
                    # original post date — closest available without a
                    # per-job detail call. Noted as a caveat, not hidden.
                    posted_at=job.get("updated_at"),
                )
            )
        return postings
