from __future__ import annotations

from datetime import datetime

from sqlmodel import select

from app.ats_adapters.ashby import AshbyAdapter
from app.ats_adapters.greenhouse import GreenhouseAdapter
from app.ats_adapters.lever import LeverAdapter
from app.ats_adapters.smartrecruiters import SmartRecruitersAdapter
from app.core.config import load_config
from app.db.models import Company, Posting
from app.db.session import get_session

# Workday deliberately excluded for now, per explicit instruction — the
# adapter (app/ats_adapters/workday.py) still exists and works for
# unprotected tenants, it's just not part of the active discovery set.
# Re-add "workday": WorkdayAdapter() here if/when you want it back.
ADAPTERS = {
    "greenhouse": GreenhouseAdapter(),
    "lever": LeverAdapter(),
    "ashby": AshbyAdapter(),
    "smartrecruiters": SmartRecruitersAdapter(),
}


def sync_companies_from_config() -> int:
    """Upsert config.yaml's companies list into the DB. Safe to run repeatedly —
    matches on (name, ats_type) and updates the token if it changed, adds new ones."""
    cfg = load_config()
    added = 0

    with get_session() as session:
        for entry in cfg.get("companies", []):
            existing = session.exec(
                select(Company).where(
                    Company.name == entry["name"], Company.ats_type == entry["ats_type"]
                )
            ).first()

            if existing is None:
                session.add(
                    Company(
                        name=entry["name"],
                        ats_type=entry["ats_type"],
                        board_token=entry["board_token"],
                        careers_url=entry.get("careers_url"),
                        active=True,
                    )
                )
                added += 1
            else:
                existing.board_token = entry["board_token"]
                existing.careers_url = entry.get("careers_url")
                session.add(existing)

        session.commit()

    return added



def _parse_posted_at(raw_value: str | None) -> datetime | None:
    """Each ATS formats its date differently — Greenhouse/Ashby give
    ISO 8601 with an offset, SmartRecruiters' releasedDate format varies
    by customer. Best-effort parse; a posting with an unparseable or
    missing date just doesn't get filtered by max_days_since_posted,
    rather than breaking discovery."""
    if not raw_value:
        return None
    try:
        return datetime.fromisoformat(raw_value.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None


def discover_all() -> dict[str, int]:
    """Poll every active company's board, upsert postings. Returns counts."""
    new_count = 0
    updated_count = 0

    with get_session() as session:
        companies = session.exec(select(Company).where(Company.active == True)).all()  # noqa: E712

        for company in companies:
            adapter = ADAPTERS.get(company.ats_type)
            if adapter is None:
                print(f"[discovery] no adapter for ats_type={company.ats_type!r}, skipping {company.name}")
                continue

            try:
                raw_postings = adapter.list_postings(company.board_token)
            except Exception as exc:  # noqa: BLE001
                print(f"[discovery] failed to fetch {company.name}: {exc}")
                continue

            for raw in raw_postings:
                existing = session.exec(
                    select(Posting).where(
                        Posting.company_id == company.id,
                        Posting.external_id == raw.external_id,
                    )
                ).first()

                if existing is None:
                    session.add(
                        Posting(
                            company_id=company.id,
                            external_id=raw.external_id,
                            title=raw.title,
                            location=raw.location,
                            remote=raw.remote,
                            url=raw.url,
                            description_raw=raw.description_raw,
                            posted_at=_parse_posted_at(raw.posted_at),
                            status="new",
                        )
                    )
                    new_count += 1
                else:
                    existing.last_seen_at = datetime.utcnow()
                    existing.description_raw = raw.description_raw
                    session.add(existing)
                    updated_count += 1

            session.commit()

    return {"new": new_count, "updated": updated_count}


def add_company_by_name(name: str) -> dict | None:
    """Auto-resolve a company's ATS via app.services.resolver and add it to
    the DB directly (no config.yaml editing needed). Returns the resolved
    info dict, or None if no ATS could be detected."""
    from app.services.resolver import resolve_company

    resolved = resolve_company(name)
    if resolved is None:
        return None

    with get_session() as session:
        existing = session.exec(
            select(Company).where(
                Company.name == name, Company.ats_type == resolved["ats_type"]
            )
        ).first()
        if existing is None:
            session.add(
                Company(
                    name=name,
                    ats_type=resolved["ats_type"],
                    board_token=resolved["board_token"],
                    active=True,
                )
            )
            session.commit()

    return resolved


def discover_companies_from_seed_list() -> dict[str, int]:
    """Auto-resolves every company in the seed list against Greenhouse,
    Lever, and Ashby, adding whichever ones actually have a live board.
    This is the 'don't make me add companies one by one' entry point —
    run it, then run discover()/match() as usual. Workday is deliberately
    not attempted here (see CLAUDE.md §0)."""
    from app.services.seed_companies import SEED_COMPANIES

    resolved_count = 0
    skipped_count = 0

    for name in SEED_COMPANIES:
        result = add_company_by_name(name)
        if result is not None:
            resolved_count += 1
        else:
            skipped_count += 1

    return {"resolved": resolved_count, "skipped": skipped_count}


def discover_via_search() -> dict[str, int]:
    """Search-based discovery via JSearch — no company list needed. Runs
    one query per title in config's titles_of_interest, combined with
    locations_ok (first entry used as the location hint; JSearch searches
    per-location, not a list). Applies remote_only / max_days_since_posted
    from config's filters block natively at the API level, so results
    already come back narrower than a blind poll would.

    Deliberately conservative on request volume — one call per title of
    interest (not per title x per location), since JSearch's free tier is
    capped. See README for how many titles = how many calls per run.
    """
    from app.services.jsearch import search as jsearch_search

    cfg = load_config()
    api_key = cfg.get("api_keys", {}).get("rapidapi_key")
    if not api_key:
        raise ValueError(
            "No RapidAPI key configured. Add api_keys.rapidapi_key to config.yaml — "
            "see README for how to get a free one."
        )

    titles = cfg.get("titles_of_interest", ["Software Engineer"])
    filters = cfg.get("filters", {}) or {}
    remote_only = filters.get("remote_only", False)
    max_days = filters.get("max_days_since_posted")
    # Use the first non-"Remote" entry in locations_ok as the location hint,
    # falling back to no location (nationwide search) if only "Remote" is listed.
    locations_ok = cfg.get("locations_ok", [])
    location_hint = next((loc for loc in locations_ok if loc.lower() != "remote"), None)

    new_count = 0
    updated_count = 0

    with get_session() as session:
        for title in titles:
            try:
                results = jsearch_search(
                    query=title,
                    api_key=api_key,
                    location=None if remote_only else location_hint,
                    remote_only=remote_only,
                    max_days_since_posted=max_days,
                )
            except Exception as exc:  # noqa: BLE001
                print(f"[jsearch] search failed for title={title!r}: {exc}")
                continue

            for result in results:
                company = session.exec(
                    select(Company).where(
                        Company.name == result.employer_name, Company.ats_type == "jsearch"
                    )
                ).first()
                if company is None:
                    company = Company(name=result.employer_name, ats_type="jsearch", board_token="")
                    session.add(company)
                    session.commit()
                    session.refresh(company)

                existing = session.exec(
                    select(Posting).where(
                        Posting.company_id == company.id, Posting.external_id == result.external_id
                    )
                ).first()

                if existing is None:
                    session.add(
                        Posting(
                            company_id=company.id,
                            external_id=result.external_id,
                            title=result.title,
                            location=result.location,
                            remote=result.remote,
                            url=result.url,
                            description_raw=result.description_raw,
                            posted_at=_parse_posted_at(result.posted_at),
                            status="new",
                        )
                    )
                    new_count += 1
                else:
                    existing.last_seen_at = datetime.utcnow()
                    session.add(existing)
                    updated_count += 1

            session.commit()

    return {"new": new_count, "updated": updated_count, "titles_searched": len(titles)}
