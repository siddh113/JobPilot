"""Lever public postings API adapter.

Docs: https://github.com/lever/postings-api
No auth required — this is Lever's official public feed for embedding
job listings on company sites.
"""
from __future__ import annotations

import httpx

from app.ats_adapters.base import RawPosting
from datetime import datetime, timezone

BASE_URL = "https://api.lever.co/v0/postings/{token}"


class LeverAdapter:
    ats_type = "lever"

    def list_postings(self, board_token: str) -> list[RawPosting]:
        url = BASE_URL.format(token=board_token)
        resp = httpx.get(url, params={"mode": "json"}, timeout=20)
        resp.raise_for_status()
        jobs = resp.json()

        postings: list[RawPosting] = []
        for job in jobs:
            categories = job.get("categories", {})
            location = categories.get("location")
            is_remote = bool(location and "remote" in location.lower()) or (
                categories.get("commitment", "").lower() == "remote"
            )
            created_at_ms = job.get("createdAt")
            posted_at = None
            if created_at_ms:
                try:
                    posted_at = datetime.fromtimestamp(int(created_at_ms) / 1000, tz=timezone.utc).isoformat()
                except (ValueError, TypeError):
                    posted_at = None
            postings.append(
                RawPosting(
                    external_id=str(job["id"]),
                    title=job.get("text", ""),
                    location=location,
                    remote=is_remote,
                    url=job.get("hostedUrl", ""),
                    description_raw=job.get("descriptionPlain", "") or job.get("description", "") or "",
                    posted_at=posted_at,
                )
            )
        return postings
