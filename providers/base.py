"""
Common job model and provider interface.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Iterable, Protocol


@dataclass
class Job:
    title: str
    url: str
    company: str
    location: str = ""
    description: str = ""
    posted_at: datetime | None = None
    remote: bool = False
    employment_type: str = ""

    # Provider-specific identifiers.
    # These are optional so existing providers continue to work.
    job_id: str = ""
    provider: str = ""
    source: str = ""


class JobProvider(Protocol):
    def fetch_jobs(self) -> Iterable[Job]:
        """
        Return jobs available from the configured company source.
        """
        ...
