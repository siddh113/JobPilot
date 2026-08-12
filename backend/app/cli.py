from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table
from sqlmodel import select

from app.db.models import Application, Company, Posting
from app.db.session import get_session, init_db
from app.services.batch import fill_batch, prepare_batch, submit_batch
from app.services.discovery import add_company_by_name, discover_all, sync_companies_from_config
from app.services.matcher import score_new_postings
from app.services.tailor import tailor_all_matched

app = typer.Typer(help="JobPilot — personal job application agent")
console = Console()


@app.command()
def initdb():
    """Create the local SQLite database and tables."""
    init_db()
    console.print("[green]Database initialized.[/green]")


@app.command(name="import-resume")
def import_resume_cmd(path: str = typer.Argument(None, help="Path to your resume file (PDF, DOCX, MD, or TXT)")):
    """Import your real resume from a file — extracts and reformats it
    into data/resume_base.md automatically. No manual transcription."""
    from app.services.resume_import import import_resume
    from app.core.config import CONFIG_PATH, ROOT
    import yaml

    if path is None:
        path = typer.prompt("Path to your resume file (PDF, DOCX, MD, or TXT)")

    src = Path(path).expanduser()
    if not src.exists():
        console.print(f"[red]No file found at {src}[/red]")
        return

    # Figure out where resume_base.md should go — from config.yaml if it
    # exists, otherwise the default location. Resolved against ROOT, not
    # cwd, so this works whether invoked from backend/ or elsewhere.
    dest = ROOT / "data" / "resume_base.md"
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH) as f:
            cfg = yaml.safe_load(f) or {}
        dest = ROOT / cfg.get("resume_path", "data/resume_base.md")

    if dest.exists():
        if not typer.confirm(f"{dest} already exists — overwrite it with the imported resume?"):
            console.print("Cancelled.")
            return

    console.print(f"Extracting text from {src.name}...")
    try:
        result_path = import_resume(str(src), str(dest))
    except Exception as exc:  # noqa: BLE001
        console.print(f"[red]Import failed:[/red] {exc}")
        return

    console.print(f"[green]Imported and saved to {result_path}.[/green]\n")
    console.print("[bold]Preview:[/bold]")
    console.print(result_path.read_text()[:1500])
    console.print(
        "\n[dim]Review the full file and fix anything the extraction got wrong "
        "before running 'match'/'tailor' — this is your source of truth for every application.[/dim]"
    )


@app.command()
def discover():
    """Poll all active companies' ATS boards for new postings."""
    init_db()
    counts = discover_all()
    console.print(f"[bold]Discovery complete[/bold] — {counts['new']} new, {counts['updated']} updated.")


@app.command(name="discover-search")
def discover_search():
    """Search-based discovery — no company list needed. Queries JSearch
    (aggregates Indeed, LinkedIn, Glassdoor, ZipRecruiter) directly by
    title + location, applying your remote/date filters natively at the
    API level. Requires api_keys.rapidapi_key in config.yaml — see README.
    This is the primary discovery path; 'discover'/'discover-companies'
    (direct ATS polling) still works alongside it and costs nothing.
    """
    init_db()
    from app.services.discovery import discover_via_search

    try:
        counts = discover_via_search()
    except ValueError as exc:
        console.print(f"[red]{exc}[/red]")
        return

    console.print(
        f"[bold]Search discovery complete[/bold] — searched {counts['titles_searched']} "
        f"title(s), {counts['new']} new posting(s), {counts['updated']} already seen."
    )


@app.command(name="sync-companies")
def sync_companies():
    """Load companies from config.yaml into the database (safe to re-run)."""
    init_db()
    added = sync_companies_from_config()
    console.print(f"[bold]Synced.[/bold] {added} new compan{'y' if added == 1 else 'ies'} added.")


@app.command(name="discover-companies")
def discover_companies():
    """Auto-resolve a curated seed list of companies against Greenhouse,
    Lever, and Ashby — the 'don't make me add companies one by one' command.
    Run this once (or whenever you want to refresh the set), then run
    'discover' and 'match' as usual. Workday is skipped for now.
    """
    init_db()
    console.print("Resolving seed companies against Greenhouse, Lever, and Ashby (this takes a bit)...")
    from app.services.discovery import discover_companies_from_seed_list

    counts = discover_companies_from_seed_list()
    console.print(
        f"[bold]Done.[/bold] [green]{counts['resolved']} resolved[/green], "
        f"{counts['skipped']} skipped (no live board found on those three platforms)."
    )


@app.command(name="add-company")
def add_company(name: str):
    """Auto-detect a company's ATS by name and add it — no manual token lookup.

    Tries Greenhouse, Lever, and Ashby's public APIs against likely slug
    guesses for the given name. Workday isn't auto-detectable this way
    (see CLAUDE.md §5) — add those manually in config.yaml.
    """
    init_db()
    console.print(f"Trying to resolve [bold]{name}[/bold] against Greenhouse, Lever, and Ashby...")
    result = add_company_by_name(name)
    if result is None:
        console.print(
            f"[red]Couldn't auto-detect an ATS for {name!r}.[/red] "
            "It may use Workday, iCIMS, or a platform without a public feed — "
            "check its careers page URL and add it manually if it's Workday."
        )
        return
    console.print(
        f"[green]Found it![/green] {name} uses [bold]{result['ats_type']}[/bold] "
        f"(token: {result['board_token']}, {result['posting_count']} open roles right now)."
    )


@app.command(name="set-filters")
def set_filters():
    """Interactively set your job filters: date posted, remote-only,
    keyword excludes/requires. Relocation/location constraints stay in
    config.yaml's locations_ok / locations_excluded — this command is for
    the rest of the constraint set. Written back into config.yaml without
    disturbing the file's existing comments."""
    from app.services.filter_config import load_filters, save_filters

    current = load_filters()
    console.print("[bold]Current filters:[/bold]")
    for k, v in current.items():
        console.print(f"  {k}: {v}")
    console.print()

    days_str = typer.prompt(
        "Only show postings from the last N days (blank = no limit)",
        default=str(current.get("max_days_since_posted") or ""),
        show_default=False,
    )
    max_days = int(days_str) if days_str.strip() else None

    remote_only = typer.confirm(
        "Remote-only?", default=bool(current.get("remote_only", False))
    )

    exclude_str = typer.prompt(
        "Exclude keywords (comma-separated, e.g. 'Staff, Principal, Clearance Required')",
        default=", ".join(current.get("exclude_keywords", [])),
        show_default=False,
    )
    exclude_keywords = [k.strip() for k in exclude_str.split(",") if k.strip()]

    require_str = typer.prompt(
        "Require at least one of these keywords (comma-separated, blank = no requirement)",
        default=", ".join(current.get("require_keywords", [])),
        show_default=False,
    )
    require_keywords = [k.strip() for k in require_str.split(",") if k.strip()]

    new_filters = {
        "max_days_since_posted": max_days,
        "remote_only": remote_only,
        "exclude_keywords": exclude_keywords,
        "require_keywords": require_keywords,
    }
    save_filters(new_filters)
    console.print("\n[green]Filters saved.[/green] They apply next time you run 'filter-postings'.")


@app.command(name="filters")
def show_filters():
    """Show your current filter settings (date posted, remote, keywords) —
    location/relocation rules live separately, see config.yaml."""
    from app.services.filter_config import load_filters

    current = load_filters()
    table = Table(title="Current filters")
    table.add_column("Filter")
    table.add_column("Value")
    for k, v in current.items():
        table.add_row(k, str(v) if v not in (None, [], "") else "(none)")
    console.print(table)
    console.print(
        "\nLocation/relocation rules (locations_ok, locations_excluded, "
        "open_to_relocate) are set separately in config.yaml."
    )


@app.command(name="filter-postings")
def filter_postings():
    """Apply your current filters to newly-discovered postings. Run this
    after 'discover' and before 'match' — filtered-out postings never get
    scored, so you're not spending LLM calls on jobs you've already ruled
    out (wrong age, wrong location, excluded keyword, etc.)."""
    init_db()
    from app.services.filters import filter_new_postings

    counts = filter_new_postings()
    console.print(
        f"[bold]Filtered.[/bold] {counts['kept']} passed and are ready for 'match', "
        f"{counts['filtered']} filtered out."
    )


@app.command()
def match():
    """Score all newly-discovered postings against your resume."""
    init_db()
    n = score_new_postings()
    console.print(f"[bold]Scored {n} postings.[/bold] Run 'digest' to see matches.")


@app.command()
def tailor():
    """Generate draft resume + cover letter for every matched posting."""
    init_db()
    ids = tailor_all_matched()
    console.print(f"[bold]Generated {len(ids)} draft application(s).[/bold] Run 'review' to approve.")


@app.command()
def review():
    """Interactively step through draft applications: approve, edit, or reject."""
    init_db()
    with get_session() as session:
        drafts = session.exec(select(Application).where(Application.status == "draft")).all()

        if not drafts:
            console.print("No drafts pending review.")
            return

        for a in drafts:
            posting = session.get(Posting, a.posting_id)
            console.rule(f"Application #{a.id} — {posting.title} ({posting.url})")
            console.print(a.tailored_resume_md or "(no resume draft)")
            console.print("\n[bold]Cover letter:[/bold]\n" + (a.tailored_cover_letter_md or "(none)"))

            choice = typer.prompt("Approve / Reject / Skip? [a/r/s]", default="s")
            if choice.lower().startswith("a"):
                a.status = "approved"
                console.print("[green]Approved.[/green] Run 'fill <id>' when ready.")
            elif choice.lower().startswith("r"):
                a.status = "rejected"
                console.print("[red]Rejected.[/red]")
            else:
                console.print("Skipped for now.")
                continue

            session.add(a)
            session.commit()


@app.command()
def digest():
    """Print a summary of today's matches and pending approvals."""
    init_db()
    with get_session() as session:
        matched = session.exec(select(Posting).where(Posting.status == "matched")).all()
        pending = session.exec(select(Application).where(Application.status == "draft")).all()

    table = Table(title="Matched postings awaiting tailoring")
    table.add_column("ID")
    table.add_column("Title")
    table.add_column("Location")
    for p in matched:
        table.add_row(str(p.id), p.title, p.location or "-")
    console.print(table)

    console.print(f"\n[bold]{len(pending)}[/bold] application draft(s) awaiting your review.")


@app.command()
def fill(application_id: int):
    """Playwright-fill one approved application's form. Stops before submit."""
    init_db()
    from app.services.fill import fill_application

    console.print(f"Filling application #{application_id} (browser will open)...")
    status = fill_application(application_id)
    console.print(f"[bold]Result: {status}[/bold]")
    if status == "filled":
        console.print("Screenshot saved to ./receipts/. Review it, then run 'submit' when ready.")
    elif status == "manual_needed":
        console.print("[yellow]Couldn't confidently auto-fill this one — finish it manually.[/yellow]")


@app.command()
def submit(application_id: int):
    """Final confirmation + submit an already-filled application."""
    init_db()
    from app.services.submit import submit_application

    with get_session() as session:
        a = session.get(Application, application_id)
        if a is None:
            console.print("[red]No such application.[/red]")
            return
        if a.status != "filled":
            console.print(f"[yellow]Application is status={a.status!r}, must be 'filled' first.[/yellow]")
            return

    if not typer.confirm(f"Submit application #{application_id} now? This is final."):
        console.print("Cancelled.")
        return

    status = submit_application(application_id)
    console.print(f"[bold]Result: {status}[/bold]")


@app.command(name="quick-apply")
def quick_apply(count: int = 6):
    """The closest thing to a single 'apply' button: tailors the top N
    matches, walks you through reviewing them, then asks for ONE confirm
    to fill all of them and ONE more confirm to actually submit all of
    them. It does not ask you to approve each of the N individually before
    filling — but it will never submit a batch you haven't seen filled and
    confirmed as a whole. See CLAUDE.md §0 for why that gate never gets
    skipped, even here.
    """
    init_db()
    console.rule(f"Quick-apply: top {count} matches")

    console.print("Tailoring drafts...")
    app_ids = prepare_batch(count)
    if not app_ids:
        console.print("[yellow]No matched postings available. Run 'discover' and 'match' first.[/yellow]")
        return
    console.print(f"[bold]{len(app_ids)} draft(s) ready.[/bold] Review each below:\n")

    with get_session() as session:
        for app_id in app_ids:
            a = session.get(Application, app_id)
            posting = session.get(Posting, a.posting_id)
            console.rule(f"#{a.id} — {posting.title} ({posting.url})")
            console.print(a.tailored_resume_md or "(no resume draft)")
            console.print("\n[bold]Cover letter:[/bold]\n" + (a.tailored_cover_letter_md or "(none)"))
            choice = typer.prompt("Approve / Reject / Skip? [a/r/s]", default="s")
            if choice.lower().startswith("a"):
                a.status = "approved"
            elif choice.lower().startswith("r"):
                a.status = "rejected"
            session.add(a)
            session.commit()

    with get_session() as session:
        approved_ids = [
            app_id for app_id in app_ids
            if session.get(Application, app_id).status == "approved"
        ]

    if not approved_ids:
        console.print("[yellow]Nothing approved — stopping here.[/yellow]")
        return

    if not typer.confirm(f"\nFill all {len(approved_ids)} approved application(s) now?"):
        console.print("Stopped. Run 'fill <id>' individually whenever you're ready.")
        return

    console.print("Filling (browser will open)...")
    fill_results = fill_batch(approved_ids)

    filled_table = Table(title="Fill results")
    filled_table.add_column("App ID")
    filled_table.add_column("Status")
    for app_id, status in fill_results.items():
        filled_table.add_row(str(app_id), status)
    console.print(filled_table)

    filled_ids = [aid for aid, s in fill_results.items() if s == "filled"]
    if not filled_ids:
        console.print("[yellow]Nothing filled successfully — nothing to submit.[/yellow]")
        return

    console.print(
        f"\n[bold]{len(filled_ids)} application(s) filled and ready.[/bold] "
        "Screenshots are in ./receipts/ — take a look before confirming."
    )
    if not typer.confirm(f"Submit all {len(filled_ids)} filled application(s) now? This is final."):
        console.print("Stopped before submitting. Run 'submit <id>' individually whenever you're ready.")
        return

    submit_results = submit_batch(filled_ids)
    result_table = Table(title="Submit results")
    result_table.add_column("App ID")
    result_table.add_column("Status")
    for app_id, status in submit_results.items():
        result_table.add_row(str(app_id), status)
    console.print(result_table)


if __name__ == "__main__":
    app()
