"""Workday adapter — calls the same CXS JSON endpoint a Workday career site's
own front-end calls to render its job list. This is not a documented public
API the way Greenhouse/Lever/Ashby are, but it's the same request the browser
makes, plain and unmodified.

Important limitation, by design (see CLAUDE.md §0): many large Workday
tenants sit behind Akamai bot management and will reject this. We do NOT
spoof headers, rotate user agents, or otherwise try to get past that — if a
tenant blocks the request, list_postings raises and that company should be
checked manually instead. This adapter only works for tenants that don't
bot-protect their public job list.
"""
from __future__ import annotations

import httpx

from app.ats_adapters.base import RawPosting


class WorkdayAdapter:
    ats_type = "workday"

    def list_postings(self, board_token: str) -> list[RawPosting]:
        """board_token format: 'tenant/wdN/site', e.g. 'hp/wd5/ExternalCareerSite'.

        Set this per-company in config.yaml by looking at the company's
        careers URL: https://{tenant}.{wdN}.myworkdayjobs.com/{site}
        """
        try:
            tenant, wd_server, site = board_token.split("/")
        except ValueError as exc:
            raise ValueError(
                f"Workday board_token must be 'tenant/wdN/site', got {board_token!r}"
            ) from exc

        url = f"https://{tenant}.{wd_server}.myworkdayjobs.com/wday/cxs/{tenant}/{site}/jobs"
        postings: list[RawPosting] = []
        offset = 0
        limit = 20

        while True:
            resp = httpx.post(
                url,
                json={"appliedFacets": {}, "limit": limit, "offset": offset, "searchText": ""},
                headers={"Content-Type": "application/json", "Accept": "application/json"},
                timeout=20,
            )
            resp.raise_for_status()  # bot-protected tenants will fail here — expected, not worked around
            data = resp.json()
            batch = data.get("jobPostings", [])

            for job in batch:
                path = job.get("externalPath", "")
                postings.append(
                    RawPosting(
                        external_id=path or job.get("bulletFields", [""])[0],
                        title=job.get("title", ""),
                        location=job.get("locationsText") or job.get("location"),
                        remote=bool(job.get("locationsText") and "remote" in job["locationsText"].lower()),
                        url=f"https://{tenant}.{wd_server}.myworkdayjobs.com/en-US/{site}{path}",
                        description_raw="",  # list endpoint doesn't include full text; detail fetch needed if desired
                    )
                )

            if len(batch) < limit or offset > 5000:  # safety cap, this is a personal tool not a crawler
                break
            offset += limit

        return postings
