"""Final submit step. Deliberately its own function, never called by
fill_application automatically — see CLAUDE.md §0. Only ever invoked after
an explicit confirmation from the person, per-application or per-batch."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from playwright.sync_api import sync_playwright

from app.db.models import Application
from app.db.session import get_session
from app.services.fill import RECEIPTS_DIR


def submit_application(application_id: int, headless: bool = True) -> str:
    """Re-opens the posting, re-fills (forms don't persist across sessions),
    and this time clicks submit. Only call this after the person has
    reviewed the filled preview and explicitly confirmed."""
    with get_session() as session:
        application = session.get(Application, application_id)
        if application is None:
            raise ValueError(f"No application with id {application_id}")
        if application.status != "filled":
            raise ValueError(
                f"Application {application_id} is status={application.status!r}, "
                "must be 'filled' (and person-confirmed) before submitting."
            )

    # Re-fill is intentionally re-run here rather than reusing the fill
    # preview's browser session, since Playwright sessions aren't kept
    # alive between CLI invocations. Same field-fill logic as fill.py.
    from app.services.fill import FIELD_LABEL_MAP, _resolve_field_value
    from app.db.models import Posting

    with get_session() as session:
        posting = session.get(Posting, application.posting_id)

    receipt_path = RECEIPTS_DIR / f"application_{application_id}_submitted.png"
    status = "failed"

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        page = browser.new_page()
        try:
            page.goto(posting.url, timeout=30000)
            page.wait_for_load_state("networkidle", timeout=15000)

            for field_key, label_variants in FIELD_LABEL_MAP.items():
                for label in label_variants:
                    try:
                        locator = page.get_by_label(label, exact=False)
                        if locator.count() > 0:
                            value = _resolve_field_value(field_key)
                            if value:
                                locator.first.fill(value)
                            break
                    except Exception:  # noqa: BLE001
                        continue

            submit_button = page.get_by_role("button", name="Submit", exact=False)
            if submit_button.count() == 0:
                print(f"[submit] No submit button found for application {application_id}; leaving for manual completion.")
                status = "manual_needed"
            else:
                submit_button.first.click()
                page.wait_for_timeout(2000)
                page.screenshot(path=str(receipt_path), full_page=True)
                status = "submitted"

        except Exception as exc:  # noqa: BLE001
            print(f"[submit] Failed to submit application {application_id}: {exc}")
            status = "failed"
        finally:
            browser.close()

    with get_session() as session:
        application = session.get(Application, application_id)
        application.status = status
        if status == "submitted":
            application.submitted_at = datetime.utcnow()
            application.receipt_path = str(receipt_path)
        session.add(application)
        session.commit()

    return status
