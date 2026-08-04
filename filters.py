"""
Job filtering logic.

Filtering is deliberately separated into:
1. keyword matching
2. location matching
3. excluded keyword matching

This makes it possible for the watcher to report exactly where a job
was filtered out.
"""

from __future__ import annotations

import re
from typing import Iterable


class JobFilter:
    def __init__(
        self,
        keywords: Iterable[str],
        locations: Iterable[str] | None = None,
        excluded_keywords: Iterable[str] | None = None,
    ) -> None:
        self.keywords = [
            str(keyword).strip()
            for keyword in keywords
            if str(keyword).strip()
        ]

        self.locations = [
            str(location).strip()
            for location in (locations or [])
            if str(location).strip()
        ]

        self.excluded_keywords = [
            str(keyword).strip()
            for keyword in (excluded_keywords or [])
            if str(keyword).strip()
        ]

    @staticmethod
    def _job_text(job) -> str:
        """
        Build the searchable text from all useful job fields.
        """
        values = [
            getattr(job, "title", ""),
            getattr(job, "description", ""),
            getattr(job, "location", ""),
            getattr(job, "employment_type", ""),
        ]

        return "\n".join(
            str(value)
            for value in values
            if value
        ).lower()

    @staticmethod
    def _contains_keyword(text: str, keyword: str) -> bool:
        """
        Perform a case-insensitive keyword search.

        For normal phrases, substring matching is useful because career
        sites often use punctuation or formatting inconsistently.
        """
        return keyword.lower() in text

    def matches_keywords(self, job) -> bool:
        """
        Return True when at least one configured keyword occurs in the job.
        """
        text = self._job_text(job)

        if not self.keywords:
            return True

        return any(
            self._contains_keyword(text, keyword)
            for keyword in self.keywords
        )

    def matches_location(self, job) -> bool:
        """
        Return True when the job passes the location filter.

        If no locations are configured, every location passes.

        If a job has no location and locations are configured, it is
        currently rejected. The diagnostic output in check_jobs.py lets
        us identify whether this is happening frequently.
        """
        if not self.locations:
            return True

        location = str(
            getattr(job, "location", "") or ""
        ).lower()

        if not location:
            return False

        return any(
            configured_location.lower() in location
            for configured_location in self.locations
        )

    def matches_exclusions(self, job) -> bool:
        """
        Return True when the job does NOT contain an excluded keyword.
        """
        if not self.excluded_keywords:
            return True

        text = self._job_text(job)

        return not any(
            self._contains_keyword(text, keyword)
            for keyword in self.excluded_keywords
        )

    def matches(self, job) -> bool:
        """
        Apply the complete filter pipeline.
        """
        if not self.matches_keywords(job):
            return False

        if not self.matches_location(job):
            return False

        if not self.matches_exclusions(job):
            return False

        return True
