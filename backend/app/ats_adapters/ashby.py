"""Ashby public job-board API adapter.

Docs: https://developers.ashbyhq.com/docs (Job Posting API)
No auth required — this is Ashby's official public feed:
GET https://api.ashbyhq.com/posting-api/job-board/{board_token}
"""
from __future__ import annotations

import httpx

from app.ats_adapters.base import RawPosting

BASE_URL = "https://api.ashbyhq.com/posting-api/job-board/{token}"


class AshbyAdapter:
    ats_type = "ashby"

    def list_postings(self, board_token: str) -> list[RawPosting]:
        url = BASE_URL.format(token=board_token)
        resp = httpx.get(url, params={"includeCompensation": "true"}, timeout=20)
        resp.raise_for_status()
        jobs = resp.json().get("jobs", [])

        postings: list[RawPosting] = []
        for job in jobs:
            location = job.get("location") or job.get("locationName")
            postings.append(
                RawPosting(
                    external_id=str(job.get("id", job.get("jobId", ""))),
                    title=job.get("title", ""),
                    location=location,
                    remote=bool(job.get("isRemote")) or bool(location and "remote" in location.lower()),
                    url=job.get("jobUrl") or job.get("applyUrl", ""),
                    description_raw=job.get("descriptionPlain", "") or job.get("description", "") or "",
                    # Confirmed field name from Ashby's own docs
                    # (developers.ashbyhq.com/docs/public-job-posting-api).
                    posted_at=job.get("publishedAt"),
                )
            )
        return postings
