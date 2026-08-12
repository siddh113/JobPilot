"""FastAPI backend for the JobPilot web UI. This wraps the exact same
services the CLI uses (app.services.*) — there is no separate logic here,
just an HTTP layer over the same pipeline, so the CLI and the web UI never
drift apart or enforce different rules. Same §0 boundaries apply: fill and
submit remain distinct endpoints, submit only accepts already-'filled'
applications, nothing here adds a bulk/no-confirm path the CLI doesn't have.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import func
from sqlmodel import select

from app.core.config import load_config
from app.db.models import Application, Company, MatchScore, Posting
from app.db.session import get_session, init_db
from app.services.geo import classify_country
from app.services.matcher import extract_skill_tags

app = FastAPI(title="JobPilot API")

# Local dev only — the frontend runs on Vite's default port, the API on
# uvicorn's. This is a personal tool running entirely on localhost.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def _startup():
    init_db()


# ---------- Schemas ----------

class PostingOut(BaseModel):
    id: int
    title: str
    company_name: str
    location: Optional[str]
    remote: bool
    url: str
    status: str
    filter_reason: Optional[str]
    final_score: Optional[float] = None
    has_application: bool = False
    posted_at: Optional[datetime] = None
    first_seen_at: Optional[datetime] = None
    description_snippet: Optional[str] = None
    skill_tags: list[str] = []


class ApplicationOut(BaseModel):
    id: int
    posting_id: int
    posting_title: str
    company_name: str
    status: str
    tailored_cover_letter_md: Optional[str]
    tailored_resume_pdf_path: Optional[str]
    tailored_cover_letter_pdf_path: Optional[str]
    receipt_path: Optional[str]


class FiltersIn(BaseModel):
    max_days_since_posted: Optional[int] = None
    remote_only: bool = False
    exclude_keywords: list[str] = []
    require_keywords: list[str] = []


class DigestOut(BaseModel):
    new: int
    filtered_out: int
    matched: int
    draft_applications: int
    approved_applications: int
    filled_applications: int
    submitted_applications: int


# ---------- Digest / overview ----------

@app.get("/api/digest", response_model=DigestOut)
def get_digest():
    with get_session() as session:
        def count_postings(status: str) -> int:
            return session.exec(
                select(func.count()).select_from(Posting).where(Posting.status == status)
            ).one()

        def count_apps(status: str) -> int:
            return session.exec(
                select(func.count()).select_from(Application).where(Application.status == status)
            ).one()

        return DigestOut(
            new=count_postings("new"),
            filtered_out=count_postings("filtered_out"),
            matched=count_postings("matched"),
            draft_applications=count_apps("draft"),
            approved_applications=count_apps("approved"),
            filled_applications=count_apps("filled"),
            submitted_applications=count_apps("submitted"),
        )


# ---------- Postings ----------

class PostingsPage(BaseModel):
    total: int
    items: list[PostingOut]


def _base_postings_query(status: Optional[str], actionable: bool, max_hours_since_posted: Optional[int]):
    """Shared status/actionable/date filtering used by both the postings
    list and the countries facet — one place defining what 'in scope'
    means, so the facet options and the actual results can't drift apart."""
    query = select(Posting)
    if status:
        query = query.where(Posting.status == status)
    if actionable:
        query = query.where(Posting.status.not_in(["filtered_out", "ignored"]))
        query = query.where(Posting.id.not_in(select(Application.posting_id)))
    if max_hours_since_posted is not None:
        cutoff = datetime.utcnow() - timedelta(hours=max_hours_since_posted)
        # Fall back to first_seen_at when a posting has no posted_at — an
        # unparsed/missing posted date shouldn't silently exclude a
        # posting, and first_seen_at is always populated. Mirrors the
        # same "unknown age doesn't hide a possible fit" rule the
        # max_days_since_posted filter already uses (filters.py).
        query = query.where(func.coalesce(Posting.posted_at, Posting.first_seen_at) >= cutoff)
    return query


def _country_matching_ids(base_query, country: str) -> set[int]:
    """Country filtering needs Python-side classification (free-text
    location, no structured geo data — see geo.py), which can't be
    expressed as a SQL WHERE clause. Fetch just the columns classification
    needs for every posting matching the *other* filters, classify in
    Python, and return the matching id set — applied as an additional
    Posting.id.in_(...) filter before COUNT/LIMIT/OFFSET so pagination and
    totals stay correct instead of being computed after a page is already
    sliced."""
    subq = base_query.subquery()
    with get_session() as session:
        rows = session.exec(select(subq.c.id, subq.c.location, subq.c.remote)).all()
    return {pid for pid, location, remote in rows if classify_country(location, remote) == country}


@app.get("/api/postings/countries", response_model=list[str])
def list_posting_countries(
    status: Optional[str] = None,
    actionable: bool = False,
    max_hours_since_posted: Optional[int] = None,
):
    """Distinct countries actually present in the current in-scope
    postings, for the country filter dropdown — options are never dead
    (0 results) and never missing a country that's genuinely there."""
    subq = _base_postings_query(status, actionable, max_hours_since_posted).subquery()
    with get_session() as session:
        rows = session.exec(select(subq.c.location, subq.c.remote)).all()
    countries = {classify_country(location, remote) for location, remote in rows}
    return sorted(countries)


@app.get("/api/postings", response_model=PostingsPage)
def list_postings(
    status: Optional[str] = None,
    actionable: bool = False,
    country: Optional[str] = None,
    max_hours_since_posted: Optional[int] = None,
    limit: int = 100,
    offset: int = 0,
):
    """actionable=true is what Browse Jobs actually wants: not filtered
    out, not skipped, not already applied to. Filtering that server-side
    (instead of over-fetching everything and filtering in the browser)
    keeps pagination meaningful — a page of `limit` rows is a page of
    `limit` genuinely-actionable postings, not `limit` rows that might
    mostly get discarded client-side."""
    try:
        resume_text = load_config()["_resume_text"]
    except FileNotFoundError:
        resume_text = ""

    query = _base_postings_query(status, actionable, max_hours_since_posted)
    if country:
        matching_ids = _country_matching_ids(query, country)
        query = query.where(Posting.id.in_(matching_ids))

    with get_session() as session:
        total = session.exec(select(func.count()).select_from(query.subquery())).one()

        page_query = query.order_by(Posting.first_seen_at.desc(), Posting.id.desc()).limit(limit).offset(offset)
        postings = session.exec(page_query).all()

        if not postings:
            return PostingsPage(total=total, items=[])

        posting_ids = [p.id for p in postings]
        company_ids = {p.company_id for p in postings}

        companies_by_id = {
            c.id: c for c in session.exec(select(Company).where(Company.id.in_(company_ids))).all()
        }

        # Latest MatchScore per posting: fetch ascending and let later rows
        # overwrite earlier ones in the dict, so each key ends up holding
        # its most-recent score without a per-posting query.
        score_rows = session.exec(
            select(MatchScore)
            .where(MatchScore.posting_id.in_(posting_ids))
            .order_by(MatchScore.scored_at.asc())
        ).all()
        latest_score_by_posting = {}
        for s in score_rows:
            latest_score_by_posting[s.posting_id] = s

        applied_posting_ids = set(
            session.exec(select(Application.posting_id).where(Application.posting_id.in_(posting_ids))).all()
        )

        results = []
        for p in postings:
            company = companies_by_id.get(p.company_id)
            score_row = latest_score_by_posting.get(p.id)
            snippet = p.description_raw[:400].strip() if p.description_raw else None
            results.append(
                PostingOut(
                    id=p.id,
                    title=p.title,
                    company_name=company.name if company else "Unknown",
                    location=p.location,
                    remote=p.remote,
                    url=p.url,
                    status=p.status,
                    filter_reason=p.filter_reason,
                    final_score=score_row.final_score if score_row else None,
                    has_application=p.id in applied_posting_ids,
                    posted_at=p.posted_at,
                    first_seen_at=p.first_seen_at,
                    description_snippet=snippet,
                    skill_tags=extract_skill_tags(resume_text, p.title, p.description_raw) if resume_text else [],
                )
            )
        return PostingsPage(total=total, items=results)


@app.post("/api/postings/{posting_id}/skip")
def skip_posting(posting_id: int):
    with get_session() as session:
        posting = session.get(Posting, posting_id)
        if posting is None:
            raise HTTPException(404, "Posting not found")
        posting.status = "ignored"
        session.add(posting)
        session.commit()
        return {"id": posting_id, "status": "ignored"}


@app.post("/api/postings/{posting_id}/apply")
def apply_to_posting(posting_id: int):
    """Tailors a resume + cover letter for this one posting and creates a
    draft Application — the person still approves it in the Applications
    tab before anything is filled or submitted. See CLAUDE.md §0."""
    from app.services.tailor import tailor_application

    with get_session() as session:
        posting = session.get(Posting, posting_id)
        if posting is None:
            raise HTTPException(404, "Posting not found")
        existing = session.exec(
            select(Application).where(Application.posting_id == posting_id)
        ).first()
        if existing is not None:
            raise HTTPException(400, "Already applied to this posting — check the Applications tab.")

    try:
        app_id = tailor_application(posting_id)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(500, f"Tailoring failed: {exc}")

    return {"application_id": app_id, "status": "draft"}


# ---------- Applications ----------

@app.get("/api/applications", response_model=list[ApplicationOut])
def list_applications(status: Optional[str] = None):
    with get_session() as session:
        query = select(Application)
        if status:
            query = query.where(Application.status == status)
        apps = session.exec(query.order_by(Application.created_at.desc())).all()

        results = []
        for a in apps:
            posting = session.get(Posting, a.posting_id)
            company = session.get(Company, posting.company_id) if posting else None
            results.append(
                ApplicationOut(
                    id=a.id,
                    posting_id=a.posting_id,
                    posting_title=posting.title if posting else "Unknown",
                    company_name=company.name if company else "Unknown",
                    status=a.status,
                    tailored_cover_letter_md=a.tailored_cover_letter_md,
                    tailored_resume_pdf_path=a.tailored_resume_pdf_path,
                    tailored_cover_letter_pdf_path=a.tailored_cover_letter_pdf_path,
                    receipt_path=a.receipt_path,
                )
            )
        return results


class ApplicationDecision(BaseModel):
    decision: str  # "approve" | "reject"


@app.post("/api/applications/{app_id}/decision")
def decide_application(app_id: int, body: ApplicationDecision):
    if body.decision not in ("approve", "reject"):
        raise HTTPException(400, "decision must be 'approve' or 'reject'")
    with get_session() as session:
        application = session.get(Application, app_id)
        if application is None:
            raise HTTPException(404, "Application not found")
        if application.status != "draft":
            raise HTTPException(400, f"Application is status={application.status!r}, must be 'draft'")
        application.status = "approved" if body.decision == "approve" else "rejected"
        session.add(application)
        session.commit()
        return {"id": app_id, "status": application.status}


@app.post("/api/applications/{app_id}/fill")
def fill_application_endpoint(app_id: int):
    from app.services.fill import fill_application

    try:
        status = fill_application(app_id, headless=True)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    return {"id": app_id, "status": status}


class TailoringOut(BaseModel):
    id: int
    posting_title: str
    company_name: str
    status: str
    resume: dict
    resume_diff: dict
    keyword_coverage: dict
    cover_letter: Optional[str]


@app.get("/api/applications/{app_id}/tailoring", response_model=TailoringOut)
def get_application_tailoring(app_id: int):
    """Everything the live tailoring/review screen needs in one call: the
    structured resume, a word-diff against the base resume for highlighting,
    and keyword coverage against the posting."""
    import json

    from app.services.resume_diff import diff_resume, keyword_coverage as compute_keyword_coverage

    with get_session() as session:
        application = session.get(Application, app_id)
        if application is None:
            raise HTTPException(404, "Application not found")
        if not application.tailored_resume_md:
            raise HTTPException(400, "This application has no tailored resume yet")
        posting = session.get(Posting, application.posting_id)
        company = session.get(Company, posting.company_id) if posting else None

    resume_data = json.loads(application.tailored_resume_md)
    base_resume_text = load_config()["_resume_text"]

    return TailoringOut(
        id=application.id,
        posting_title=posting.title if posting else "Unknown",
        company_name=company.name if company else "Unknown",
        status=application.status,
        resume=resume_data,
        resume_diff=diff_resume(resume_data, base_resume_text),
        keyword_coverage=compute_keyword_coverage(
            resume_data, posting.title if posting else "", posting.description_raw if posting else ""
        ),
        cover_letter=application.tailored_cover_letter_md,
    )


class ReviseIn(BaseModel):
    instruction: str


class ReviseOut(BaseModel):
    resume: dict
    resume_diff: dict
    keyword_coverage: dict
    explanation: str


@app.post("/api/applications/{app_id}/revise", response_model=ReviseOut)
def revise_application_endpoint(app_id: int, body: ReviseIn):
    """Chat-style resume editing: one free-text instruction, grounded in
    the same base resume and posting as the original tailoring — see
    CLAUDE.md §1 (no invented experience)."""
    from app.services.resume_diff import diff_resume, keyword_coverage as compute_keyword_coverage
    from app.services.tailor import revise_application

    if not body.instruction.strip():
        raise HTTPException(400, "instruction cannot be empty")

    try:
        resume_data, explanation = revise_application(app_id, body.instruction)
    except ValueError as exc:
        raise HTTPException(400, str(exc))

    with get_session() as session:
        application = session.get(Application, app_id)
        posting = session.get(Posting, application.posting_id)

    base_resume_text = load_config()["_resume_text"]

    return ReviseOut(
        resume=resume_data,
        resume_diff=diff_resume(resume_data, base_resume_text),
        keyword_coverage=compute_keyword_coverage(
            resume_data, posting.title if posting else "", posting.description_raw if posting else ""
        ),
        explanation=explanation,
    )


class SubmitConfirmation(BaseModel):
    confirmed: bool


@app.post("/api/applications/{app_id}/submit")
def submit_application_endpoint(app_id: int, body: SubmitConfirmation):
    # The confirmation happens in the UI (a modal the person must actively
    # click through) — this flag just makes the requirement explicit in
    # the API contract too, so no client can submit without it.
    if not body.confirmed:
        raise HTTPException(400, "Submission requires confirmed=true — this is a final, real action.")
    from app.services.submit import submit_application

    try:
        status = submit_application(app_id, headless=True)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    return {"id": app_id, "status": status}


# ---------- Pipeline actions ----------

@app.post("/api/actions/discover-search")
def action_discover_search():
    from app.services.discovery import discover_via_search

    try:
        return discover_via_search()
    except ValueError as exc:
        raise HTTPException(400, str(exc))


@app.post("/api/actions/discover-companies")
def action_discover_companies():
    from app.services.discovery import discover_companies_from_seed_list

    return discover_companies_from_seed_list()


@app.post("/api/actions/discover")
def action_discover():
    from app.services.discovery import discover_all

    return discover_all()


@app.post("/api/actions/filter-postings")
def action_filter_postings():
    from app.services.filters import filter_new_postings

    return filter_new_postings()


@app.post("/api/actions/match")
def action_match():
    from app.services.matcher import score_new_postings

    return {"scored": score_new_postings()}


@app.post("/api/actions/tailor")
def action_tailor():
    from app.services.tailor import tailor_all_matched

    return {"application_ids": tailor_all_matched()}


class BatchApplyIn(BaseModel):
    count: int = 6


@app.post("/api/actions/prepare-batch")
def action_prepare_batch(body: BatchApplyIn):
    from app.services.batch import prepare_batch

    return {"application_ids": prepare_batch(body.count)}


class BatchIdsIn(BaseModel):
    application_ids: list[int]


@app.post("/api/actions/fill-batch")
def action_fill_batch(body: BatchIdsIn):
    """Fills every already-approved application in the batch. No external
    effect — nothing gets submitted here. See CLAUDE.md §0: this is the one
    batch-level confirmation the UI shows before anything gets filled."""
    from app.services.batch import fill_batch

    return {"results": fill_batch(body.application_ids)}


class BatchSubmitIn(BaseModel):
    application_ids: list[int]
    confirmed: bool


@app.post("/api/actions/submit-batch")
def action_submit_batch(body: BatchSubmitIn):
    # Same hard requirement as the single-application submit endpoint —
    # batching several applications together never collapses this into a
    # zero-review action. See CLAUDE.md §0.
    if not body.confirmed:
        raise HTTPException(400, "Submitting a batch requires confirmed=true — this is final, real, and irreversible per item.")
    from app.services.batch import submit_batch

    return {"results": submit_batch(body.application_ids)}


# ---------- Filters ----------

@app.get("/api/filters", response_model=FiltersIn)
def get_filters():
    from app.services.filter_config import load_filters

    return FiltersIn(**load_filters())


@app.put("/api/filters")
def set_filters(body: FiltersIn):
    from app.services.filter_config import save_filters

    save_filters(body.model_dump())
    return {"ok": True}


# ---------- Resume ----------

@app.post("/api/resume/import")
async def import_resume_endpoint(file: UploadFile = File(...)):
    import tempfile
    from pathlib import Path
    from app.services.resume_import import import_resume
    from app.core.config import ROOT, CONFIG_PATH
    import yaml

    suffix = Path(file.filename).suffix
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(await file.read())
        tmp_path = tmp.name

    dest = ROOT / "data" / "resume_base.md"
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH) as f:
            cfg = yaml.safe_load(f) or {}
        dest = ROOT / cfg.get("resume_path", "data/resume_base.md")

    try:
        result_path = import_resume(tmp_path, str(dest))
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(400, str(exc))

    return {"saved_to": str(result_path), "preview": result_path.read_text()[:2000]}


@app.get("/api/resume")
def get_resume():
    from app.core.config import load_config

    try:
        cfg = load_config()
    except FileNotFoundError as exc:
        raise HTTPException(400, str(exc))
    return {"content": cfg["_resume_text"]}
