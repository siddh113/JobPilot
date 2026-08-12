"""Fills a Greenhouse application form via Playwright. Stops before the
submit click every time (see CLAUDE.md §0) — this only fills and screenshots.

Honesty note: Greenhouse's application-form DOM has changed over the years
(older boards.greenhouse.io iframe embeds vs. newer job-boards.greenhouse.io
React forms) and can still vary per-company custom questions. This uses
label-text matching rather than hardcoded field IDs so it's resilient to
most of that, but it has NOT been run against a live posting yet — this
sandbox can't reach job-boards.greenhouse.io. Run it against one real
posting first and expect to adjust selectors in `FIELD_LABEL_MAP` before
trusting it broadly.

No CAPTCHA solving, no bot-detection evasion. If the form doesn't yield to
straightforward field-matching, this marks the application manual_needed
and stops — it does not retry with different fingerprints or headers.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from playwright.sync_api import sync_playwright

from app.db.models import Application, Posting
from app.db.session import get_session

RECEIPTS_DIR = Path(__file__).resolve().parents[3] / "receipts"
RECEIPTS_DIR.mkdir(exist_ok=True)

# Maps our known applicant fields to likely visible label text on the form.
# Playwright's get_by_label does fuzzy/partial matching, which is why this
# works across Greenhouse's several form-generator versions without needing
# exact DOM IDs.
FIELD_LABEL_MAP = {
    "first_name": ["First Name"],
    "last_name": ["Last Name"],
    "email": ["Email"],
    "phone": ["Phone"],
}


def fill_application(application_id: int, headless: bool = True) -> str:
    """Fills the Greenhouse form for an approved application.
    Returns the resulting status: 'filled' or 'manual_needed'."""
    with get_session() as session:
        application = session.get(Application, application_id)
        if application is None:
            raise ValueError(f"No application with id {application_id}")
        if application.status != "approved":
            raise ValueError(
                f"Application {application_id} is status={application.status!r}, "
                "must be 'approved' before filling."
            )
        posting = session.get(Posting, application.posting_id)

        # Capture these as plain values now — the object will expire after
        # the next commit (SQLAlchemy's default expire_on_commit), and
        # reading expired attributes from a detached instance later would
        # silently raise inside the broad except blocks below.
        posting_url = posting.url
        resume_pdf_path = application.tailored_resume_pdf_path
        cover_letter_pdf_path = application.tailored_cover_letter_pdf_path
        cover_letter_text = application.tailored_cover_letter_md

    with get_session() as session:
        application = session.get(Application, application_id)
        application.status = "filling"
        session.add(application)
        session.commit()

    status = "manual_needed"
    screenshot_path = RECEIPTS_DIR / f"application_{application_id}_prefill.png"

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=headless)
            page = browser.new_page()

            try:
                page.goto(posting_url, timeout=30000)
                page.wait_for_load_state("networkidle", timeout=15000)

                filled_any = False
                for field_key, label_variants in FIELD_LABEL_MAP.items():
                    for label in label_variants:
                        try:
                            locator = page.get_by_label(label, exact=False)
                            if locator.count() > 0:
                                value = _resolve_field_value(field_key)
                                if value:
                                    locator.first.fill(value)
                                    filled_any = True
                                break
                        except Exception:  # noqa: BLE001 — field not on this form, try next label/skip
                            continue

                # Resume upload — the tailored PDF generated at tailor-time,
                # matching the base resume's layout. Cover letter uploads to
                # a second file input if the form has one; most Greenhouse
                # forms only have a single resume upload plus a cover-letter
                # textarea, handled separately below if present.
                try:
                    file_inputs = page.locator('input[type="file"]')
                    if file_inputs.count() > 0 and resume_pdf_path:
                        file_inputs.first.set_input_files(resume_pdf_path)
                        filled_any = True
                    if file_inputs.count() > 1 and cover_letter_pdf_path:
                        file_inputs.nth(1).set_input_files(cover_letter_pdf_path)
                except Exception as exc:  # noqa: BLE001
                    print(f"[fill] Resume/cover-letter file upload failed: {exc}")

                # Cover letter as a text field, if the form has one instead of
                # a second file upload.
                try:
                    cover_field = page.get_by_label("Cover Letter", exact=False)
                    if cover_field.count() > 0 and cover_letter_text:
                        cover_field.first.fill(cover_letter_text)
                        filled_any = True
                except Exception as exc:  # noqa: BLE001
                    print(f"[fill] Cover letter text fill failed: {exc}")

                page.screenshot(path=str(screenshot_path), full_page=True)
                status = "filled" if filled_any else "manual_needed"

            except Exception as exc:  # noqa: BLE001
                print(f"[fill] Could not fill application {application_id}: {exc}")
                status = "manual_needed"
            finally:
                # Deliberately NOT clicking submit here. Ever. See CLAUDE.md §0.
                browser.close()

    except Exception as exc:  # noqa: BLE001 — browser launch itself failed
        print(f"[fill] Could not launch browser for application {application_id}: {exc}")
        status = "manual_needed"

    with get_session() as session:
        application = session.get(Application, application_id)
        application.status = status
        application.receipt_path = str(screenshot_path) if screenshot_path.exists() else None
        session.add(application)
        session.commit()

    return status


def _resolve_field_value(field_key: str) -> str | None:
    """Pulls applicant field values from config — kept separate from the
    resume content so personal contact info lives in one place."""
    from app.core.config import load_config

    cfg = load_config()
    applicant = cfg.get("applicant", {})
    return applicant.get(field_key)
