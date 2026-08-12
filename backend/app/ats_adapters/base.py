from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass
class RawPosting:
    external_id: str
    title: str
    location: str | None
    remote: bool
    url: str
    description_raw: str
    posted_at: str | None = None  # ISO 8601 string if the ATS provides one, else None


class ATSAdapter(Protocol):
    ats_type: str

    def list_postings(self, board_token: str) -> list[RawPosting]:
        """Return all currently-listed postings for a company's board."""
        ...
