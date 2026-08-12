# JobPilot

Personal job-application agent. Full spec lives in [CLAUDE.md](./CLAUDE.md) —
read that first, especially §0 (non-negotiable boundaries).

Two ways to use it: the **CLI** (always available, no setup beyond Python)
or the **web UI** (FastAPI + React, same pipeline, visual review).

## Setup (do this once)

```bash
cd backend
pip install -r requirements.txt --break-system-packages
playwright install chromium

cp ../config.example.yaml ../config.yaml
mkdir -p ../data

export ANTHROPIC_API_KEY=sk-...   # required — tailoring/import won't work without it

python -m app.cli initdb
python -m app.cli import-resume ~/Downloads/YourResume.pdf   # or .docx/.md/.txt
```

## Option A: CLI

```bash
python -m app.cli discover-search   # pulls postings by title/location, no company list
python -m app.cli filter-postings   # apply your date/remote/keyword filters
python -m app.cli match             # score against your resume
python -m app.cli tailor            # generate draft resume + cover letter for matches
python -m app.cli review            # approve/reject drafts interactively
python -m app.cli digest            # summary view
python -m app.cli quick-apply       # tailor top N, review, fill, submit — see CLAUDE.md §0
```

`discover-search` needs `api_keys.rapidapi_key` in `config.yaml` — get a
free key at rapidapi.com (search "JSearch", subscribe to the free Basic
plan, no credit card required).

## Option B: Web UI

Two terminals, both from the project root:

```bash
# Terminal 1 — backend API
cd backend
uvicorn app.api.main:app --reload --port 8000

# Terminal 2 — frontend
cd frontend
npm install   # first time only
npm run dev
```

Open **http://localhost:5173**. The pipeline stepper at the top is the
main navigation — click a stage (Discover, Filter, Match, Tailor, Review,
Fill, Submit) to see what's in it. The action buttons below it run the
same steps as the CLI commands above. Settings (resume upload, filters)
live behind the "Settings" button top-right.

**Fill and submit run headless — no browser window opens.** Review what
got filled via the screenshot in `./receipts/`, referenced directly in the
submit confirmation modal, rather than watching a browser live.

## Notes

`discover` / `discover-companies` are a free, no-API-key supplementary
discovery path (direct polling of Greenhouse/Lever/Ashby/SmartRecruiters),
alongside `discover-search`'s broader LinkedIn/Indeed/Glassdoor coverage.

`fill` and `submit` are real (Playwright-based), tested against a local
mock form and verified to actually populate fields correctly — but not yet
run against a live ATS page. Run `fill <id>` (CLI) or the Fill button (web
UI) against one real posting first and expect to adjust `FIELD_LABEL_MAP`
in `app/services/fill.py` if a real company's form differs from what was
tested.

Submission always requires an explicit confirmation — the CLI asks, the
web UI shows a modal, and the API itself rejects an unconfirmed submit
request. This holds in every entry point, not just the one you're using
right now — see CLAUDE.md §0.
