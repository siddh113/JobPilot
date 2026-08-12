from __future__ import annotations

import re

from sqlmodel import select

from app.core.config import load_config
from app.db.models import MatchScore, Posting
from app.db.session import get_session


def _tokenize(text: str) -> set[str]:
    return set(re.findall(r"[a-zA-Z][a-zA-Z0-9+.#]{1,}", text.lower()))


# Canonical display names for a curated set of recognizable tech/skill
# tokens. Used only to *label* real overlap between resume and posting
# text (see extract_skill_tags) — never to invent a skill that isn't
# actually present in both.
SKILL_VOCAB = {
    "python": "Python", "javascript": "JavaScript", "typescript": "TypeScript",
    "react": "React", "node": "Node.js", "java": "Java", "c#": "C#", "c++": "C++",
    "go": "Go", "golang": "Go", "rust": "Rust", "sql": "SQL", "nosql": "NoSQL",
    "aws": "AWS", "gcp": "GCP", "azure": "Azure", "docker": "Docker",
    "kubernetes": "Kubernetes", "terraform": "Terraform", "graphql": "GraphQL",
    "rest": "REST APIs", "api": "APIs", "kafka": "Kafka", "redis": "Redis",
    "postgres": "PostgreSQL", "postgresql": "PostgreSQL", "mongodb": "MongoDB",
    "mysql": "MySQL", "git": "Git", "linux": "Linux", "bash": "Bash",
    "ci": "CI/CD", "pandas": "Pandas", "numpy": "NumPy", "pytorch": "PyTorch",
    "tensorflow": "TensorFlow", "llm": "LLM", "nlp": "NLP", "ml": "ML",
    "ai": "AI", "agile": "Agile", "scrum": "Scrum", "html": "HTML", "css": "CSS",
    "vue": "Vue.js", "angular": "Angular", "django": "Django", "flask": "Flask",
    "fastapi": "FastAPI", "spring": "Spring", "microservices": "Microservices",
    "etl": "ETL",
}


def extract_skill_tags(resume_text: str, posting_title: str, posting_desc: str, limit: int = 4) -> list[str]:
    """Tags a posting card with skills that genuinely overlap between the
    resume and the posting text, ordered by first appearance in the
    posting (title, then description)."""
    resume_tokens = _tokenize(resume_text)
    combined = posting_title + " " + posting_desc
    ordered_tokens = re.findall(r"[a-zA-Z][a-zA-Z0-9+.#]{1,}", combined.lower())

    tags: list[str] = []
    for tok in ordered_tokens:
        canon = SKILL_VOCAB.get(tok)
        if canon and tok in resume_tokens and canon not in tags:
            tags.append(canon)
        if len(tags) >= limit:
            break
    return tags


def location_score(posting_location: str | None, cfg) -> float:
    """Location fit scoring. Explicit exclusions (non-US offices) are a hard
    filter regardless of open_to_relocate — this is a US-only job search.
    Within the US, a listed preferred city/remote gets a bonus; anywhere
    else in the US gets a smaller bonus if open_to_relocate is true."""
    open_to_relocate = cfg.get("open_to_relocate", False)
    locations_ok = [loc.lower() for loc in cfg.get("locations_ok", [])]
    locations_excluded = [loc.lower() for loc in cfg.get("locations_excluded", [])]

    if not posting_location:
        return 0.0

    loc_lower = posting_location.lower()

    if any(bad in loc_lower for bad in locations_excluded):
        return -1000.0  # hard exclude — non-US, overrides open_to_relocate

    if any(ok in loc_lower for ok in locations_ok):
        return 15.0  # preferred US city or remote — clear bonus
    if open_to_relocate:
        return 5.0  # elsewhere in the US, relocation acceptable
    return -10.0  # not preferred and not open to relocating — small penalty


def heuristic_score(resume_text: str, posting_title: str, posting_desc: str, cfg, posting_location: str | None = None) -> float:
    resume_tokens = _tokenize(resume_text)
    posting_tokens = _tokenize(posting_title + " " + posting_desc)

    if not posting_tokens:
        return 0.0

    overlap = resume_tokens & posting_tokens
    skill_score = min(len(overlap) / max(len(posting_tokens), 1) * 300, 60)  # cap contribution

    title_score = 0.0
    title_lower = posting_title.lower()
    for interest in cfg.get("titles_of_interest", []):
        if interest.lower() in title_lower or any(
            word in title_lower for word in interest.lower().split()
        ):
            title_score = 25.0
            break

    loc_score = location_score(posting_location, cfg)

    return round(max(0.0, min(skill_score + title_score + loc_score, 100.0)), 1)


def llm_score(posting_title: str, posting_desc: str, resume_summary: str) -> tuple[float, str]:
    """Borderline-only LLM fit scoring. Returns (score, reasoning)."""
    from anthropic import Anthropic

    client = Anthropic()
    prompt = f"""You are scoring how well a candidate fits a job posting, 0-100.
Be strict: only score high if the candidate's real background genuinely matches.

Candidate resume summary:
{resume_summary}

Job title: {posting_title}
Job description:
{posting_desc[:4000]}

Respond in exactly this format:
SCORE: <integer 0-100>
REASON: <one sentence>"""

    resp = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=200,
        messages=[{"role": "user", "content": prompt}],
    )
    text = "".join(block.text for block in resp.content if block.type == "text")

    score_match = re.search(r"SCORE:\s*(\d+)", text)
    reason_match = re.search(r"REASON:\s*(.+)", text)
    score = float(score_match.group(1)) if score_match else 0.0
    reason = reason_match.group(1).strip() if reason_match else ""
    return score, reason


def score_new_postings() -> int:
    cfg = load_config()
    resume_text = cfg["_resume_text"]
    threshold = cfg.get("match_threshold", 70)
    scored = 0

    with get_session() as session:
        postings = session.exec(select(Posting).where(Posting.status == "new")).all()

        for posting in postings:
            h_score = heuristic_score(resume_text, posting.title, posting.description_raw, cfg, posting.location)
            final = h_score
            reasoning = None

            if 40 <= h_score <= 75:
                try:
                    l_score, reasoning = llm_score(posting.title, posting.description_raw, resume_text[:1000])
                    final = (h_score + l_score) / 2
                except Exception as exc:  # noqa: BLE001
                    print(f"[matcher] LLM scoring failed for posting {posting.id}: {exc}")

            session.add(
                MatchScore(
                    posting_id=posting.id,
                    heuristic_score=h_score,
                    llm_score=None,
                    final_score=final,
                    reasoning=reasoning,
                )
            )
            posting.status = "matched" if final >= threshold else "scored"
            session.add(posting)
            scored += 1

        session.commit()

    return scored
