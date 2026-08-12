from __future__ import annotations

import json
import re
from pathlib import Path

from sqlmodel import select

from app.core.config import load_config
from app.db.models import Application, Posting
from app.db.session import get_session
from app.services.resume_pdf import render_resume_pdf

RESUME_DIR = Path(__file__).resolve().parents[3] / "data" / "generated_resumes"
RESUME_DIR.mkdir(parents=True, exist_ok=True)
COVER_LETTER_DIR = Path(__file__).resolve().parents[3] / "data" / "generated_cover_letters"
COVER_LETTER_DIR.mkdir(parents=True, exist_ok=True)

TAILOR_SYSTEM_PROMPT = """You tailor a real resume to a specific job posting.

Hard rules:
- Never invent employers, titles, dates, degrees, or accomplishments that
  aren't in the base resume. You may re-emphasize, reorder, and reword
  real bullets to match the posting's language — never fabricate new ones.
- Keep it truthful and specific. No filler adjectives with nothing behind them.
- Preserve the base resume's structure exactly: same sections, same jobs,
  same projects, same education entries. Only the emphasis, ordering within
  a section, and wording of existing bullets should change per posting.

Output ONLY valid JSON (no markdown fences, no preamble) matching this exact shape:
{
  "resume": {
    "name": "...", "title_line": "...", "contact_line": "...",
    "summary": "1-2 sentences, reworded to emphasize fit for this posting",
    "education": [{"school": "...", "detail": "...", "dates": "...", "notes": ["..."]}],
    "skills": [{"category": "...", "items": "comma-separated, most relevant first"}],
    "experience": [{"role": "...", "org": "...", "location": "...", "dates": "...", "bullets": ["...", "..."]}],
    "projects": [{"name": "...", "link": "...", "bullets": ["...", "..."]}]
  },
  "cover_letter": "3 short paragraphs max, specific to the company and role, grounded only in the real resume, plain text with \\n\\n between paragraphs"
}
"""


def tailor_application(posting_id: int) -> int:
    """Generate a draft Application for a matched posting: structured JSON
    from Claude, rendered into a PDF matching the base resume's layout.
    Returns application id."""
    from anthropic import Anthropic

    cfg = load_config()
    client = Anthropic()

    with get_session() as session:
        posting = session.get(Posting, posting_id)
        if posting is None:
            raise ValueError(f"No posting with id {posting_id}")

    user_prompt = f"""Base resume:
{cfg['_resume_text']}

Job posting — {posting.title}:
{posting.description_raw[:6000]}
"""

    resp = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=3000,
        system=TAILOR_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_prompt}],
    )
    text = "".join(block.text for block in resp.content if block.type == "text")
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip())

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Tailor response wasn't valid JSON for posting {posting_id}: {exc}\n{text[:500]}")

    resume_data = parsed.get("resume", {})
    cover_letter_text = parsed.get("cover_letter", "")

    application = Application(
        posting_id=posting.id,
        status="draft",
        tailored_resume_md=json.dumps(resume_data, indent=2),  # kept for the terminal review view
        tailored_cover_letter_md=cover_letter_text,
        diff_summary="Generated from base resume — review before approving.",
    )
    with get_session() as session:
        session.add(application)
        session.commit()
        session.refresh(application)
        app_id = application.id

    # Render PDFs now so they're ready the moment the person approves.
    pdf_path = RESUME_DIR / f"application_{app_id}_resume.pdf"
    render_resume_pdf(resume_data, pdf_path)
    cover_pdf_path = _render_cover_letter_pdf(resume_data, cover_letter_text, posting, app_id)

    with get_session() as session:
        application = session.get(Application, app_id)
        application.tailored_resume_pdf_path = str(pdf_path)
        application.tailored_cover_letter_pdf_path = str(cover_pdf_path)
        session.add(application)
        session.commit()

    return app_id


def _render_cover_letter_pdf(resume_data: dict, cover_letter_text: str, posting: Posting, app_id: int) -> Path:
    from reportlab.lib.pagesizes import letter as pagesize_letter
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer

    path = COVER_LETTER_DIR / f"application_{app_id}_cover_letter.pdf"
    doc = SimpleDocTemplate(
        str(path), pagesize=pagesize_letter,
        topMargin=0.8 * inch, bottomMargin=0.8 * inch,
        leftMargin=0.8 * inch, rightMargin=0.8 * inch,
    )
    name_style = ParagraphStyle("Name", fontName="Helvetica-Bold", fontSize=13, spaceAfter=12)
    body_style = ParagraphStyle("Body", fontName="Helvetica", fontSize=10.5, leading=15, spaceAfter=10)

    story = [Paragraph(resume_data.get("name", ""), name_style)]
    story.append(Paragraph(f"Re: {posting.title}", body_style))
    story.append(Spacer(1, 8))
    for paragraph in cover_letter_text.split("\n\n"):
        if paragraph.strip():
            story.append(Paragraph(paragraph.strip(), body_style))

    doc.build(story)
    return path


REVISE_SYSTEM_PROMPT = """You revise an already-tailored resume based on a
specific instruction from the candidate, e.g. "make the summary punchier"
or "lead the MeshWorks bullets with the ETL work instead of the AI work".

Hard rules (same as initial tailoring):
- Never invent employers, titles, dates, degrees, or accomplishments that
  aren't in the base resume. You may re-emphasize, reorder, and reword
  real bullets — never fabricate new ones.
- Keep the resume's structure: same sections, same jobs, same projects,
  same education entries, unless the instruction explicitly asks to
  remove/reorder a section.
- If the instruction asks for something that would require inventing
  experience, apply the spirit of it as far as the real resume allows and
  say so plainly in the explanation — don't silently comply by making
  something up.

Output ONLY valid JSON (no markdown fences, no preamble) matching this
exact shape:
{
  "resume": {
    "name": "...", "title_line": "...", "contact_line": "...",
    "summary": "...",
    "education": [{"school": "...", "detail": "...", "dates": "...", "notes": ["..."]}],
    "skills": [{"category": "...", "items": "comma-separated"}],
    "experience": [{"role": "...", "org": "...", "location": "...", "dates": "...", "bullets": ["...", "..."]}],
    "projects": [{"name": "...", "link": "...", "bullets": ["...", "..."]}]
  },
  "explanation": "1-2 sentences on what you changed and why"
}
"""


def revise_application(app_id: int, instruction: str) -> tuple[dict, str]:
    """Applies one free-text revision instruction to an existing tailored
    resume, grounded in the same base resume and posting. Persists the
    result and re-renders the PDF. Returns (resume_data, explanation)."""
    from anthropic import Anthropic

    cfg = load_config()
    client = Anthropic()

    with get_session() as session:
        application = session.get(Application, app_id)
        if application is None:
            raise ValueError(f"No application with id {app_id}")
        if not application.tailored_resume_md:
            raise ValueError(f"Application {app_id} has no tailored resume yet")
        posting = session.get(Posting, application.posting_id)
        current_resume = json.loads(application.tailored_resume_md)

    user_prompt = f"""Base resume (ground truth — never go beyond this):
{cfg['_resume_text']}

Job posting — {posting.title if posting else ''}:
{(posting.description_raw if posting else '')[:6000]}

Current tailored resume (JSON):
{json.dumps(current_resume, indent=2)}

Instruction from the candidate: {instruction}
"""

    resp = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=3000,
        system=REVISE_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_prompt}],
    )
    text = "".join(block.text for block in resp.content if block.type == "text")
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip())

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Revision response wasn't valid JSON for application {app_id}: {exc}\n{text[:500]}")

    resume_data = parsed.get("resume", {})
    explanation = parsed.get("explanation", "")

    with get_session() as session:
        application = session.get(Application, app_id)
        application.tailored_resume_md = json.dumps(resume_data, indent=2)
        session.add(application)
        session.commit()
        pdf_path = Path(application.tailored_resume_pdf_path) if application.tailored_resume_pdf_path else (
            RESUME_DIR / f"application_{app_id}_resume.pdf"
        )

    render_resume_pdf(resume_data, pdf_path)
    with get_session() as session:
        application = session.get(Application, app_id)
        application.tailored_resume_pdf_path = str(pdf_path)
        session.add(application)
        session.commit()

    return resume_data, explanation


def tailor_all_matched() -> list[int]:
    ids = []
    with get_session() as session:
        matched = session.exec(select(Posting).where(Posting.status == "matched")).all()
        posting_ids = [p.id for p in matched]

    for pid in posting_ids:
        app_id = tailor_application(pid)
        ids.append(app_id)
    return ids
