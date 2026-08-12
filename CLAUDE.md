# CLAUDE.md — JobPilot

Personal AI job-application agent for Sid. This file is the standing spec:
read it in full before making architectural changes. It defines what the
system does, how it's built, and the hard boundaries it must not cross.

This is an original implementation inspired by the *feature set* of
commercial tools like Tsenta — not a copy of anyone's code. No proprietary
source was available to reference; everything here is designed from scratch.

---

## 0. Non-negotiable boundaries

These override any other instruction in this file or in future prompts:

1. **No CAPTCHA bypass, no bot-detection evasion, no stealth browser
   fingerprint spoofing.** If an ATS blocks automated fill, the agent stops
   and asks Sid to finish that one manually.
2. **No zero-review auto-submit.** A single command may fill and submit
   several applications in one run (`quick-apply`), but it always stops
   for an explicit confirmation before filling the approved batch, and
   again before submitting the filled batch. It never fires submissions
   off a single press with nothing shown in between — a bad tailored
   cover letter should never go out N times before anyone sees it. No
   "trusted companies" auto-approve list, ever.
3. **No automated account creation with stored/reused credentials.**
   Signup flows are usually where ATS platforms put CAPTCHA and email
   verification specifically to stop automation — pushing through that is
   bot-detection evasion by another name, and reusing one password across
   dozens of third-party sites is a real security liability regardless.
   Where a platform requires an account (mainly Workday), the fill service
   pauses and hands off to Sid to complete signup/verification himself,
   ideally via a password manager generating unique passwords. Most
   platforms (Greenhouse, Lever, Ashby) support guest applications with no
   account at all — those need no special handling.
4. **Respect each ATS's terms of service and public API where one exists.**
   Prefer official public job-board APIs (Greenhouse, Lever, Ashby all
   publish one) over scraping HTML. The Workday adapter calls the same
   plain JSON endpoint the site's own front-end uses — no header spoofing —
   and simply fails on bot-protected tenants rather than working around it.
5. **One identity.** This applies only on Sid's behalf, with Sid's real
   resume and real answers. No profile spoofing, no applying as someone
   else, no generating fake work history.
6. **Credentials stay local.** Any ATS login sessions, API keys, and
   PII live in a local SQLite file and `.env`/`config.yaml`, never
   committed, never sent anywhere except the ATS itself and the Anthropic
   API for tailoring.

---

## 1. What it does (feature parity target)

| Feature | Behavior |
|---|---|
| **Discovery** | Polls a configurable list of companies' public job-board feeds on a schedule. New postings are diffed against the last poll. |
| **Matching** | Each new posting is scored against Sid's resume (skills overlap, title similarity, seniority fit, location/remote fit) — cheap heuristic first, LLM score only for borderline cases to save tokens. |
| **Tailoring** | For postings above the match threshold, generate a tailored resume bullet-set and cover letter draft via Claude, grounded in Sid's real resume — no invented experience. |
| **Review queue** | Every generated application sits in a queue with a diff view (base resume vs. tailored version) until Sid approves, edits, or rejects it. |
| **Fill + submit** | On approval, Playwright drives the actual ATS form: login, fields, file upload, open-ended questions answered in Sid's voice. Submit button is a separate, explicit final confirmation step. |
| **Tracking** | Every application (drafted, approved, submitted, rejected, skipped) is logged with status, timestamps, and a receipt (screenshot + confirmation text) on submit. |
| **Digest** | Daily summary of new matches and pending approvals — CLI output for v1; can grow into email/Slack later. |

Explicitly **out of scope for v1**: mobile apps, Chrome extension, iMessage/
WhatsApp surfaces, MCP server, multi-user auth, on-device model inference.
Those are listed in §7 as future phases, not built now.

---

## 2. Architecture

```
                         ┌─────────────────────┐
                         │   scheduler (cron)   │
                         └──────────┬───────────┘
                                    ▼
┌────────────┐    ┌───────────────────────────┐    ┌─────────────┐
│ ATS         │───▶│  discovery service        │───▶│  postings   │
│ adapters    │    │  (poll, diff, dedupe)      │    │  (SQLite)   │
│ (Greenhouse,│    └──────────┬────────────────┘    └─────────────┘
│  Lever, ...)│               ▼
└────────────┘    ┌───────────────────────────┐
                   │  matcher service           │
                   │  heuristic score + LLM tie-│
                   │  breaker for borderline     │
                   └──────────┬────────────────┘
                              ▼ (score ≥ threshold)
                   ┌───────────────────────────┐
                   │  tailor service (Claude)   │──▶ tailored_applications
                   │  resume bullets + cover ltr│    (SQLite, status=draft)
                   └──────────┬────────────────┘
                              ▼
                   ┌───────────────────────────┐
                   │  review CLI / review UI    │  Sid approves/edits/rejects
                   └──────────┬────────────────┘
                              ▼ (status=approved)
                   ┌───────────────────────────┐
                   │  fill service (Playwright) │  fills form, screenshots,
                   │  STOPS before submit click │  waits for final confirm
                   └──────────┬────────────────┘
                              ▼ (Sid confirms)
                   ┌───────────────────────────┐
                   │  submit + receipt          │  status=submitted, logs
                   └───────────────────────────┘
```

## 3. Tech stack

- **Backend**: Python 3.11, FastAPI (for the local review UI's API), SQLModel
  over SQLite (single file, zero-ops for a personal tool).
- **Browser automation**: Playwright (Python), headed mode by default so Sid
  can watch/intervene.
- **LLM**: Anthropic API (`claude-sonnet-4-6`), used for (a) borderline match
  scoring, (b) resume/cover-letter tailoring, (c) open-ended question
  answers — always grounded with the real resume in context, never freeform.
- **Scheduler**: simple `cron` or `launchd` calling a CLI entrypoint; no
  need for Celery/queues at this scale (dozens of postings/day, not
  thousands).
- **Frontend**: defer to CLI + a minimal FastAPI+HTMX review page for v1.
  A React dashboard is a v2 nice-to-have (§7), not required to be useful.

## 4. Data model (SQLite, via SQLModel)

```
Company(id, name, ats_type, board_token, careers_url, active)
Posting(id, company_id, external_id, title, location, remote, url,
        description_raw, first_seen_at, last_seen_at, status)
        # status: new | scored | matched | ignored | closed
MatchScore(id, posting_id, heuristic_score, llm_score, final_score,
           reasoning, scored_at)
Application(id, posting_id, status, base_resume_version,
            tailored_resume_md, tailored_cover_letter_md,
            answers_json, diff_summary, created_at, approved_at,
            submitted_at, receipt_path, notes)
            # status: draft | approved | rejected | filling | filled |
            #         submitted | failed | manual_needed
ResumeVersion(id, content_md, created_at, is_base)
```

## 5. ATS adapters (`backend/app/ats_adapters/`)

Common interface:

```python
class ATSAdapter(Protocol):
    ats_type: str
    def list_postings(self, board_token: str) -> list[RawPosting]: ...
    def fetch_posting_detail(self, external_id: str) -> RawPosting: ...
    def get_application_fields(self, external_id: str) -> list[FormField]: ...
```

**v1 adapters** (all have official public JSON APIs — no scraping needed):
Greenhouse, Lever, Ashby, and SmartRecruiters are auto-detectable by
company name via `app/services/resolver.py` — `add-company "Company Name"`
tries all four against likely slug guesses and reports which one hit.
Workday can't be auto-detected this way (its token is a `tenant/wdN/site`
triple, not a guessable slug) — add those manually with the real careers
URL, and it's currently excluded from the active adapter set anyway (see
below).

- `greenhouse.py` — `GET https://boards-api.greenhouse.io/v1/boards/{token}/jobs`
  Official public API, no auth.
- `lever.py` — `GET https://api.lever.co/v0/postings/{token}?mode=json`
  Official public API, no auth.
- `ashby.py` — `GET https://api.ashbyhq.com/posting-api/job-board/{token}`
  Official public API, no auth. Ashby's own docs; supports `includeCompensation=true`.
- `smartrecruiters.py` — `GET https://api.smartrecruiters.com/v1/companies/{token}/postings`
  Official public Postings API per SmartRecruiters' own developer docs, no
  auth. Caveat noted in their docs: it's tier-dependent — not every
  SmartRecruiters customer has this feed enabled — so some companies will
  just resolve to zero results here, same graceful-fail as any slug guess
  that doesn't hit. The list endpoint doesn't include full job
  descriptions (a second per-job detail call is needed for that); left
  blank here rather than firing N extra requests per discovery run — the
  matcher still has title + location to work with.
- `workday.py` — `POST https://{tenant}.{wdN}.myworkdayjobs.com/wday/cxs/{tenant}/{site}/jobs`
  Not a documented public API — this is the same JSON request a Workday
  career site's own front-end makes to render its listings, called plain
  and unmodified. **Deliberately does not spoof headers, rotate user
  agents, or otherwise try to get past bot protection** (see §0). Many
  large Workday tenants sit behind Akamai and will simply fail here — that
  failure is expected and correct, not a bug to work around. `board_token`
  for this adapter is `"tenant/wdN/site"` (read off the company's actual
  careers URL), not a single slug like the others. **Currently excluded
  from the active `ADAPTERS` dict in both `discovery.py` and
  `resolver.py`, and from seed discovery**, per explicit instruction — the
  code still works, it's just not wired in. Re-add it to both dicts when
  wanted again.

**On third-party scraper APIs (e.g. Apify):** deliberately not used.
Every Apify "job scraper" actor that supports a given ATS is, under the
hood, calling that same ATS's own free public API — the exact endpoints
above. Paying per-result for data available for free, with less visibility
into what's actually happening server-side, is a worse trade in every way
that matters here. The only place a third-party scraper adds real
coverage is platforms *without* a public API, which in practice means
either fighting bot protection or scraping through terms that can't be
verified — both against §0. If a specific ATS turns out to have a genuine
official public feed (as SmartRecruiters did when checked), build a direct
adapter for it instead — same pattern as the four above.

**Still unsupported:** iCIMS has no clean equivalent public JSON endpoint
pattern — add only if/when a specific target company needs it, and
re-check the §0 boundaries before doing so.

## 5b. Search-based discovery (`backend/app/services/jsearch.py`)

The primary discovery path is `discover-search`, not company polling —
this is deliberate, per explicit instruction: no manually curated company
list. It calls JSearch (via RapidAPI/OpenWeb Ninja), one query per title
in `titles_of_interest`, and searches across Indeed, LinkedIn, Glassdoor,
ZipRecruiter, and Bayt in a single call via Google for Jobs' index.

**What this actually is, honestly:** JSearch is a commercial, publicly
sold API — this project calls it as a paying/free-tier customer, the same
way it'd call any data vendor. It is not Claude (or this codebase) scraping
those platforms directly, and no bot-detection evasion is implemented here
— JSearch's own infrastructure does that aggregation, and using their
product doesn't require re-verifying their methods any more than using
any other commercial data API would. Worth understanding this distinction
rather than treating it as identical to the Apify decision in §5 — that
was declined specifically because it added no capability beyond free
official ATS APIs already integrated directly; JSearch adds real
capability (LinkedIn/Indeed/Glassdoor coverage with zero company curation)
that no free official API provides.

**Request budget:** the free tier is capped (roughly 200 req/month per
RapidAPI's Basic plan). `discover_via_search()` makes exactly one request
per `titles_of_interest` entry per run — with the default 5 titles, that's
5 requests per `discover-search` call. Don't loop this into a tight
schedule without checking the plan's actual cap.

**Company records for JSearch results** get created on the fly
(`ats_type="jsearch"`, empty `board_token`) since there's no company list
to pre-register against — they're just for grouping postings by employer
in the DB, not for further ATS polling.

The direct ATS adapters (§5) still work and cost nothing — `discover` /
`discover-companies` remain available as a free supplementary path, they
just aren't the primary flow anymore.

## 5c. Filter system (`backend/app/services/filters.py`)

A hard pre-filter step that runs between `discover` and `match` — postings
that fail never reach the matcher, so they never cost an LLM call and
never show up in `digest`. Configured via `python -m app.cli set-filters`
(interactive) or by hand-editing the `filters:` block in `config.yaml`.

Filters supported:
- **max_days_since_posted** — uses each ATS's own posted-date field
  (Greenhouse `updated_at`, Lever `createdAt`, Ashby `publishedAt`,
  SmartRecruiters `releasedDate` — field names confirmed against each
  platform's own docs). A posting with no parseable date skips this
  filter rather than getting excluded — an unknown age shouldn't hide a
  possible fit.
- **remote_only** — posting must be flagged remote by its source ATS.
- **exclude_keywords** / **require_keywords** — simple case-insensitive
  substring match against title + description. Practical for things like
  excluding `"Staff"`/`"Director"`/`"Security Clearance"` or requiring a
  specific tech keyword.
- **Location/relocation** — reuses `locations_excluded` from the matcher
  (§6) as the single source of truth, so there's one place that defines
  "out of scope geographically," not two that could drift apart.

Every filtered-out posting keeps its `filter_reason` on the `Posting` row
(status becomes `filtered_out`) — filtering is never silent, "why didn't
I see this job" always has a concrete answer.

`set-filters` writes back into `config.yaml` via `ruamel.yaml` rather than
plain `pyyaml`, specifically so it doesn't strip the file's existing
comments on every save.

## 6. Matching logic

1. **Heuristic pass (free, instant)**: keyword/skill overlap between resume
   skills list and posting text; title similarity; seniority match from
   years-of-experience phrases; location/remote compatibility.
   Score 0–100.
2. **LLM pass (only for 40–75 heuristic band)**: send posting text + resume
   summary to Claude, ask for a 0–100 fit score with 1-sentence reasoning.
   Keeps token spend low by skipping obvious yes/no cases.
3. **Threshold**: postings scoring ≥ 70 final move to tailoring. Configurable
   in `config.yaml`.

## 6a. Web UI (`backend/app/api/`, `frontend/`)

A FastAPI backend (`app/api/main.py`) wraps the exact same service
functions the CLI calls — `app.services.discovery`, `.matcher`, `.tailor`,
`.fill`, `.submit`, `.filters`, `.filter_config`, `.resume_import`. There
is no separate business logic in the API layer; it's an HTTP surface over
the same pipeline, specifically so the CLI and the web UI can never
enforce different rules or drift apart. The §0 boundaries hold identically
in both: `POST /api/applications/{id}/submit` requires `confirmed: true`
in the request body and returns 400 without it — the UI's confirmation
modal is not the only thing enforcing that, the API does too.

The React frontend (`frontend/`, Vite + React + Tailwind v4) is organized
around three tabs:

- **Jobs** — every actionable posting (not filtered out, not skipped, not
  already applied to) as a match-ring card with company badge, skill tags
  (`extract_skill_tags()` in `matcher.py` — genuine resume/posting token
  overlap, never invented), relative posted-time, and a filter bar (search,
  workplace, company, sort). Filters only cover fields the schema actually
  has — no degree/experience/visa filters, since `Posting` doesn't carry
  that data and nothing here fabricates it. **Skip** sets the posting to
  `ignored` (`POST /api/postings/{id}/skip`) and removes the card. **Apply**
  opens `TailoringModal`: it calls `POST /api/postings/{id}/apply`
  (still runs `tailor_application()` synchronously, still creates the
  draft immediately — the modal's loading animation is just UI dressing
  around the same blocking call, not a job queue), then
  `GET /api/applications/{id}/tailoring` for a word-diffed resume view
  (`resume_diff.py` — added/changed spans only, base-only text is never
  shown struck through) plus JD keyword coverage. A chat box
  (`POST /api/applications/{id}/revise`, `tailor.py::revise_application`)
  lets Sid ask for free-text edits, grounded in the same base resume and
  hard rules as initial tailoring (§1 — no invented experience). Closing
  the modal at any point after the draft exists behaves like confirming
  it (the draft's already in the Applications tab either way). A posting
  can only be applied to once — the endpoint 400s on a second attempt.
- **Applications** — every application not yet declined. Approving a
  draft (`POST .../decision`) immediately chains into filling it
  (`POST .../fill`) in the same click — filling has no external effect
  (nothing gets submitted), so there's no safety reason to make it a
  separate manual step. **Submit stays its own explicit, confirmed
  action** — a modal that points at the fill receipt screenshot and
  requires clicking "Yes, submit," and the API independently rejects a
  submit request without `confirmed: true` regardless of what the UI
  sends. This is the one boundary that never collapses, no matter how
  many other clicks get chained together elsewhere — including in the
  batch flow below.
- **Quick apply** (`ActionBar` → count input → `BatchQueueModal`) — the
  web UI's version of the CLI's `quick-apply`. Tailors the top N matches
  (`prepare_batch`), then steps through them one at a time (Prev/Next,
  same resume-diff/keyword/chat view as the single-apply modal) for
  individual approve/reject. Once at least one is approved, **one**
  confirmation fills the whole approved set (`POST /api/actions/fill-batch`
  → `batch.fill_batch`); the per-item fill results are shown before **one
  more** explicit confirmation submits the whole filled set
  (`POST /api/actions/submit-batch`, requires `confirmed: true`, mirrors
  the single-submit endpoint's rejection of unconfirmed requests). No path
  from tailoring to submission skips either confirmation, and nothing
  auto-advances past a submit click.
- **Settings** — resume upload/import and filter constraints.

Live counts (Jobs badge = new + matched postings, Applications badge =
draft + approved + filled) come from `/api/digest` and refresh after every
action via a shared refresh-tick counter in `App.jsx`.

Fill and submit run **headless by default** (`headless=True` in both
`fill_application()` and `submit_application()`, and in the API endpoints
that call them) — no browser window opens. Review happens via the
screenshot receipt saved to `./receipts/`, not by watching the browser
live. Pass `headless=False` explicitly (CLI: not currently exposed as a
flag, would need adding; API: change the hardcoded call) if watching it
happen live is ever wanted for debugging a new ATS's form.

Running both: two terminals, `uvicorn app.api.main:app --reload` from
`backend/` and `npm run dev` from `frontend/` — see README. No single
combined dev command was set up (the stack mixes Python and Node process
management, and two plain terminals is more transparent/debuggable than a
wrapper script hiding that).

## 7. Future phases (not built in v1)

- More ATS adapters (Workday re-enabled, iCIMS) if a specific target
  company needs them.
- Notification surface (email digest or Slack DM) instead of pull-only.
- MCP server wrapping the same services, so Claude Code/Claude Desktop
  can query "any new matches?" or "approve #42" conversationally.

Each phase should get its own short spec addendum here before starting —
don't build ahead of what's actually needed.

## 8. Config (`config.yaml`, gitignored — real one has Sid's data)

```yaml
resume_path: ./data/resume_base.md
companies:
  - name: Example Co
    ats_type: greenhouse
    board_token: examplecoinc
match_threshold: 70
locations_ok: ["New York, NY", "Remote", "Remote - US"]
titles_of_interest: ["AI Engineer", "Software Engineer", "Full Stack Engineer"]
```

## 9. Commands

```
python -m app.cli initdb            # create the local DB
python -m app.cli discover-search   # PRIMARY: search-based discovery (JSearch), no company list
python -m app.cli discover-companies  # supplementary: auto-resolve seed list against 4 ATS platforms
python -m app.cli add-company NAME  # supplementary: auto-detect one company's ATS by name
python -m app.cli sync-companies    # supplementary: load config.yaml companies into the DB
python -m app.cli discover          # supplementary: poll all companies, store new postings
python -m app.cli set-filters       # interactively set date/remote/keyword filters
python -m app.cli filters           # show current filter settings
python -m app.cli filter-postings   # apply filters to new postings, before match
python -m app.cli match             # score filtered postings against your resume
python -m app.cli tailor            # generate drafts for matched postings
python -m app.cli review            # interactive CLI approve/reject/edit
python -m app.cli fill <app_id>     # Playwright fill, stop before submit
python -m app.cli submit <app_id>   # final confirm + submit + receipt
python -m app.cli quick-apply       # top-N matches -> review -> 1 fill confirm -> 1 submit confirm
python -m app.cli digest            # print today's summary
```

`quick-apply` is the "one button" flow: it tailors the top N matches (6 by
default — tunable via `--count`), walks through each for individual
approve/reject (same as `review`), then asks ONE confirmation to fill the
whole approved set and ONE more to submit the whole filled set. See §0 for
why those two confirmations never get collapsed into zero.

## 10. Testing

- Adapters: unit tests against recorded fixture JSON (no live network in
  CI) — `backend/tests/fixtures/`.
- Matcher: unit tests with known resume/posting pairs and expected score
  bands.
- Fill service: never tested against real ATS in CI; manual/local only,
  since it drives a real browser against real third-party sites.
