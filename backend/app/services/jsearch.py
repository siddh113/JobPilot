"""JSearch (RapidAPI / OpenWeb Ninja) client — search-based job discovery.

Honesty note on what this actually is: JSearch is a commercial, publicly
sold API that aggregates postings from Indeed, LinkedIn, Glassdoor,
ZipRecruiter, and Bayt by reading Google for Jobs' index — not official
partnerships with those platforms. This project calls JSearch as a paying
(or free-tier) API customer, the same way it would call any data vendor;
it does not scrape any of those sites directly and does not implement any
bot-detection evasion itself. That distinction matters and is worth
understanding before relying on this.

Docs: https://rapidapi.com/letscrape-6bRBa3QguO5/api/jsearch
Endpoint: GET https://jsearch.p.rapidapi.com/search
Auth: X-RapidAPI-Key header (get one free at rapidapi.com — see README).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

import httpx

BASE_URL = "https://jsearch.p.rapidapi.com/search"


@dataclass
class SearchPosting:
    external_id: str
    title: str
    employer_name: str
    location: str | None
    remote: bool
    url: str
    description_raw: str
    posted_at: str | None
    source: str  # e.g. "indeed", "linkedin" — which upstream board it came from


def _map_date_posted(max_days_since_posted: int | None) -> str:
    """JSearch's date_posted param takes named buckets, not arbitrary day
    counts — map our config's day count to the closest bucket without
    over-promising precision."""
    if max_days_since_posted is None:
        return "all"
    if max_days_since_posted <= 1:
        return "today"
    if max_days_since_posted <= 3:
        return "3days"
    if max_days_since_posted <= 7:
        return "week"
    return "month"


def search(
    query: str,
    api_key: str,
    location: str | None = None,
    remote_only: bool = False,
    max_days_since_posted: int | None = None,
    country: str = "us",
    num_pages: int = 1,
) -> list[SearchPosting]:
    """One JSearch query. `query` should be a natural search string like
    'AI Engineer' — combine with `location` for something like searching
    'AI Engineer in New York', matching how JSearch expects queries."""
    full_query = f"{query} in {location}" if location else query

    headers = {
        "X-RapidAPI-Key": api_key,
        "X-RapidAPI-Host": "jsearch.p.rapidapi.com",
    }
    params = {
        "query": full_query,
        "page": "1",
        "num_pages": str(num_pages),
        "country": country,
        "date_posted": _map_date_posted(max_days_since_posted),
    }
    if remote_only:
        params["remote_jobs_only"] = "true"

    resp = httpx.get(BASE_URL, headers=headers, params=params, timeout=30)
    resp.raise_for_status()
    payload = resp.json()

    results: list[SearchPosting] = []
    for job in payload.get("data", []):
        city = job.get("job_city")
        state = job.get("job_state")
        location_str = ", ".join(p for p in [city, state] if p) or job.get("job_country")

        results.append(
            SearchPosting(
                external_id=str(job.get("job_id", "")),
                title=job.get("job_title", ""),
                employer_name=job.get("employer_name", "Unknown"),
                location=location_str,
                remote=bool(job.get("job_is_remote")),
                url=job.get("job_apply_link", ""),
                description_raw=job.get("job_description", "") or "",
                posted_at=job.get("job_posted_at_datetime_utc"),
                source=job.get("job_publisher", "unknown"),
            )
        )
    return results
