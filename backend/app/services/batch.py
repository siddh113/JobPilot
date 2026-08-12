"""The 'apply to top N matches' flow. This is the closest thing to a single
button — but per CLAUDE.md §0, it stops for one batch-level review before
filling and one more before submitting. It does not ask you to confirm each
of the N applications individually, but it also never fires N submissions
off a single press with zero review in between: a mistake in a tailored
cover letter would otherwise go out N times before anyone saw it.
"""
from __future__ import annotations

from sqlmodel import select

from app.db.models import Application, Posting
from app.db.session import get_session
from app.services.fill import fill_application
from app.services.submit import submit_application
from app.services.tailor import tailor_application


def get_batch_candidates(count: int) -> list[int]:
    """Returns posting IDs for the top `count` matched-but-not-yet-tailored
    postings, highest score first. The docstring always said
    "not-yet-tailored" but the query never actually excluded postings that
    already had an Application — tailoring stays status="matched" forever,
    so a second batch run (or the "Tailor matched" pipeline button) would
    happily re-tailor and duplicate an application that already existed.
    The explicit exclusion here is the fix."""
    from app.db.models import MatchScore

    with get_session() as session:
        rows = session.exec(
            select(Posting, MatchScore)
            .join(MatchScore, MatchScore.posting_id == Posting.id)
            .where(Posting.status == "matched")
            .where(Posting.id.not_in(select(Application.posting_id)))
            .order_by(MatchScore.final_score.desc())
        ).all()

    seen = set()
    ordered_ids = []
    for posting, _score in rows:
        if posting.id not in seen:
            seen.add(posting.id)
            ordered_ids.append(posting.id)
        if len(ordered_ids) >= count:
            break
    return ordered_ids


def prepare_batch(count: int) -> list[int]:
    """Tailors the top `count` matches. Returns application IDs — still in
    'draft' status, nothing filled or submitted yet."""
    posting_ids = get_batch_candidates(count)
    app_ids = []
    for pid in posting_ids:
        app_id = tailor_application(pid)
        app_ids.append(app_id)
    return app_ids


def fill_batch(application_ids: list[int]) -> dict[int, str]:
    """Fills every application in the batch (each must already be
    'approved' by the person via `review`). Returns {app_id: status}.
    Does NOT submit anything — see submit_batch."""
    results = {}
    for app_id in application_ids:
        try:
            status = fill_application(app_id)
        except Exception as exc:  # noqa: BLE001
            print(f"[batch] fill failed for application {app_id}: {exc}")
            status = "failed"
        results[app_id] = status
    return results


def submit_batch(application_ids: list[int]) -> dict[int, str]:
    """Submits every application in the batch that reached 'filled' status.
    Only call this after the person has reviewed the whole filled batch and
    given one explicit confirmation — see cli.py apply_batch command."""
    results = {}
    for app_id in application_ids:
        with get_session() as session:
            application = session.get(Application, app_id)
            if application is None or application.status != "filled":
                results[app_id] = "skipped"
                continue
        try:
            status = submit_application(app_id)
        except Exception as exc:  # noqa: BLE001
            print(f"[batch] submit failed for application {app_id}: {exc}")
            status = "failed"
        results[app_id] = status
    return results
