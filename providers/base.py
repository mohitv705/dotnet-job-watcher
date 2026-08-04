"""
Shared Job record used by every provider.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class Job:
    title: str
    url: str
    company: str = ""
    location: str = ""
    description: str = ""
    posted_at: str = ""
    remote: Optional[bool] = None
    employment_type: str = ""
