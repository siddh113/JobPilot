"""Word-level diff between the base resume and a tailored resume, plus
keyword-coverage scoring against a posting. Both feed the review UI's
highlighted-resume view — everything here is derived from real text
already in the DB/config, nothing invented.
"""
from __future__ import annotations

import difflib
import re

from app.services.matcher import SKILL_VOCAB

_WORD_RE = re.compile(r"\S+|\s+")


def _split_words(text: str) -> list[str]:
    return _WORD_RE.findall(text or "")


def _diff_segments(tailored_text: str, base_lines: list[str]) -> list[dict]:
    """Word-diff `tailored_text` against whichever base_lines entry it most
    resembles. Segments only ever mark words as added/changed (green) —
    base-only words that got dropped aren't shown, since they're not part
    of the tailored text being rendered."""
    if not tailored_text or not tailored_text.strip():
        return [{"text": tailored_text or "", "added": False}]

    best = difflib.get_close_matches(tailored_text, base_lines, n=1, cutoff=0.0)
    base_line = best[0] if best else ""

    a_words = _split_words(base_line)
    b_words = _split_words(tailored_text)
    sm = difflib.SequenceMatcher(a=a_words, b=b_words, autojunk=False)

    segments = []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            segments.append({"text": "".join(b_words[j1:j2]), "added": False})
        elif tag in ("replace", "insert"):
            segments.append({"text": "".join(b_words[j1:j2]), "added": True})
        # "delete" = words only in the base line — not part of the
        # tailored output, so nothing to render.
    return segments


def diff_resume(resume_data: dict, base_resume_text: str) -> dict:
    """Returns a structure shaped like resume_data, but every free-text
    field is replaced by a list of {"text", "added"} segments for
    highlighting. Structural fields (dates, org, school, links) are passed
    through unchanged — those aren't tailored, so there's nothing to diff."""
    base_lines = [ln for ln in base_resume_text.splitlines() if ln.strip()]

    out: dict = {
        "name": resume_data.get("name", ""),
        "title_line": resume_data.get("title_line", ""),
        "contact_line": resume_data.get("contact_line", ""),
    }

    if resume_data.get("summary"):
        out["summary_segments"] = _diff_segments(resume_data["summary"], base_lines)

    out["education"] = [
        {
            "school": edu.get("school", ""),
            "detail": edu.get("detail", ""),
            "dates": edu.get("dates", ""),
            "notes": edu.get("notes", []),
        }
        for edu in resume_data.get("education", [])
    ]

    out["skills"] = [
        {
            "category": group.get("category", ""),
            "items_segments": _diff_segments(group.get("items", ""), base_lines),
        }
        for group in resume_data.get("skills", [])
    ]

    out["experience"] = [
        {
            "role": job.get("role", ""),
            "org": job.get("org", ""),
            "location": job.get("location", ""),
            "dates": job.get("dates", ""),
            "bullet_segments": [_diff_segments(b, base_lines) for b in job.get("bullets", [])],
        }
        for job in resume_data.get("experience", [])
    ]

    out["projects"] = [
        {
            "name": proj.get("name", ""),
            "link": proj.get("link", ""),
            "bullet_segments": [_diff_segments(b, base_lines) for b in proj.get("bullets", [])],
        }
        for proj in resume_data.get("projects", [])
    ]

    return out


def extract_posting_keywords(posting_title: str, posting_desc: str, limit: int = 16) -> list[str]:
    """The JD's own vocabulary (not filtered by the resume) — this is the
    denominator for 'N of M keywords covered'."""
    tokens = re.findall(r"[a-zA-Z][a-zA-Z0-9+.#]{1,}", f"{posting_title} {posting_desc}".lower())
    seen: list[str] = []
    for tok in tokens:
        canon = SKILL_VOCAB.get(tok)
        if canon and canon not in seen:
            seen.append(canon)
        if len(seen) >= limit:
            break
    return seen


def keyword_coverage(resume_data: dict, posting_title: str, posting_desc: str, limit: int = 16) -> dict:
    import json

    keywords = extract_posting_keywords(posting_title, posting_desc, limit)
    resume_text = json.dumps(resume_data).lower()
    covered = [k for k in keywords if k.lower() in resume_text]
    return {
        "covered": covered,
        "keywords": keywords,
        "covered_count": len(covered),
        "total_count": len(keywords),
    }
