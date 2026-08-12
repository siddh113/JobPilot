"""SQLModel data models for JobPilot. See CLAUDE.md §4 for the schema spec."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlmodel import Field, SQLModel


class Company(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    ats_type: str  # "greenhouse" | "lever"
    board_token: str
    careers_url: Optional[str] = None
    active: bool = True


class Posting(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    company_id: int = Field(foreign_key="company.id", index=True)
    external_id: str
    title: str
    location: Optional[str] = None
    remote: bool = False
    url: str
    description_raw: str = ""
    posted_at: Optional[datetime] = None
    first_seen_at: datetime = Field(default_factory=datetime.utcnow, index=True)
    last_seen_at: datetime = Field(default_factory=datetime.utcnow)
    status: str = Field(default="new", index=True)  # new | scored | matched | ignored | closed | filtered_out
    filter_reason: Optional[str] = None


class MatchScore(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    posting_id: int = Field(foreign_key="posting.id", index=True)
    heuristic_score: float
    llm_score: Optional[float] = None
    final_score: float
    reasoning: Optional[str] = None
    scored_at: datetime = Field(default_factory=datetime.utcnow)


class ResumeVersion(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    content_md: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    is_base: bool = False


class Application(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    # unique=True: one application per posting, ever, enforced at the DB
    # level — not just an app-level check-then-act guard, which is a race
    # (two near-simultaneous tailor_application() calls can both pass a
    # "does one exist yet?" check before either commits). This is what
    # actually stops the duplicate, not just the check in tailor.py.
    posting_id: int = Field(foreign_key="posting.id", unique=True)
    status: str = "draft"
    # draft | approved | rejected | filling | filled | submitted | failed | manual_needed
    base_resume_version: Optional[int] = Field(default=None, foreign_key="resumeversion.id")
    tailored_resume_md: Optional[str] = None
    tailored_resume_pdf_path: Optional[str] = None
    tailored_cover_letter_md: Optional[str] = None
    tailored_cover_letter_pdf_path: Optional[str] = None
    answers_json: Optional[str] = None
    diff_summary: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    approved_at: Optional[datetime] = None
    submitted_at: Optional[datetime] = None
    receipt_path: Optional[str] = None
    notes: Optional[str] = None
