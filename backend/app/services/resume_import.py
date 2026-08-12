"""Imports a real resume file (PDF, DOCX, or plain text/markdown) and
converts it into the structured resume_base.md this project's tailor
service expects — no manual transcription needed.

Grounding rule: the structuring step is explicitly told to reformat only,
never invent or embed anything not present in the extracted text. This
mirrors the same "never fabricate" rule the tailor service follows.
"""
from __future__ import annotations

from pathlib import Path

RESUME_STRUCTURE_PROMPT = """You convert a resume's extracted text into a clean markdown file.

Hard rules:
- Never invent, infer, or embellish anything not present in the source text.
- If a section (e.g. Projects) doesn't exist in the source, omit it — don't invent one.
- Preserve every real detail: dates, metrics, tool names, exact numbers.
- Fix only obvious extraction artifacts (broken line wraps, stray bullet
  characters) — don't rewrite or rephrase the actual content.

Output ONLY the markdown resume, no preamble or commentary, in this structure:

# Full Name

Title line (e.g. "AI Engineer | Full-Stack Software Engineer")
Contact line (location | phone | links, whatever the source has)

## Summary
(if present in source)

## Education
- **School** — Degree, details (GPA if present) — Dates
  - Coursework/notes if present

## Skills
- **Category**: comma-separated items
(group however the source resume groups them; if ungrouped, use one "Skills" line)

## Experience
### Role, Company — Location (Dates)
- bullet
- bullet

## Projects
### Project Name (link if present)
- bullet
- Tools: ...
"""


def extract_text_from_pdf(path: Path) -> str:
    import pdfplumber

    text_parts = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            text_parts.append(page.extract_text() or "")
    return "\n".join(text_parts)


def extract_text_from_docx(path: Path) -> str:
    import mammoth

    with open(path, "rb") as f:
        result = mammoth.extract_raw_text(f)
    return result.value


def extract_text(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return extract_text_from_pdf(path)
    if suffix == ".docx":
        return extract_text_from_docx(path)
    if suffix in (".md", ".txt"):
        return path.read_text()
    raise ValueError(f"Unsupported resume file type: {suffix} (use .pdf, .docx, .md, or .txt)")


def structure_resume(raw_text: str) -> str:
    """Sends extracted text to Claude to reformat into resume_base.md's
    structure. Grounded strictly in the source text — see RESUME_STRUCTURE_PROMPT."""
    from anthropic import Anthropic

    client = Anthropic()
    resp = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=3000,
        system=RESUME_STRUCTURE_PROMPT,
        messages=[{"role": "user", "content": f"Extracted resume text:\n\n{raw_text}"}],
    )
    return "".join(block.text for block in resp.content if block.type == "text").strip()


def import_resume(source_path: str, dest_path: str) -> Path:
    """Full pipeline: extract -> structure -> write to dest_path. Returns
    the dest Path. Does not overwrite dest_path if it already exists —
    caller (CLI) is responsible for confirming overwrite with the person."""
    src = Path(source_path).expanduser()
    if not src.exists():
        raise FileNotFoundError(f"No file at {src}")

    raw_text = extract_text(src)
    if not raw_text.strip():
        raise ValueError(
            f"Extracted no text from {src} — it may be a scanned/image-only PDF. "
            "Try exporting a text-based version, or paste the content into a .md file directly."
        )

    structured = structure_resume(raw_text)

    dest = Path(dest_path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(structured)
    return dest
