"""
Post-fetch filtering: location, remote-only, extra required/excluded
keywords, and experience level. Applied on top of the base .NET/C#/backend
keyword match in check_jobs.py.

A company entry in companies.yaml can define its own "filters:" block,
which fully replaces the global "filters:" block for that company. If a
company defines no filters block, the global one applies.
"""

from dataclasses import dataclass, field
from typing import List

from providers.base import Job


@dataclass
class JobFilter:
    locations: List[str] = field(default_factory=list)         # match ANY (substring, case-insensitive)
    remote_only: bool = False
    keywords_include: List[str] = field(default_factory=list)  # ALL must appear in title/description
    keywords_exclude: List[str] = field(default_factory=list)  # job dropped if ANY appear
    experience_levels: List[str] = field(default_factory=list) # match ANY (substring, case-insensitive)

    def matches(self, job: Job) -> bool:
        haystack = f"{job.title}\n{job.description}\n{job.location}".lower()

        if self.locations and not any(loc.lower() in job.location.lower() for loc in self.locations):
            return False

        if self.remote_only:
            is_remote = job.remote if job.remote is not None else ("remote" in job.location.lower())
            if not is_remote:
                return False

        if self.keywords_include and not all(kw.lower() in haystack for kw in self.keywords_include):
            return False

        if self.keywords_exclude and any(kw.lower() in haystack for kw in self.keywords_exclude):
            return False

        if self.experience_levels and not any(lvl.lower() in haystack for lvl in self.experience_levels):
            return False

        return True


def filter_from_config(cfg: dict) -> JobFilter:
    if not cfg:
        return JobFilter()
    return JobFilter(
        locations=cfg.get("locations") or [],
        remote_only=bool(cfg.get("remote_only", False)),
        keywords_include=cfg.get("keywords_include") or [],
        keywords_exclude=cfg.get("keywords_exclude") or [],
        experience_levels=cfg.get("experience_levels") or [],
    )
