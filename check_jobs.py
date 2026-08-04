#!/usr/bin/env python3

"""
dotnet-job-watcher
-------------------
Checks a list of target companies' job boards for postings matching
.NET/C#/backend keywords (plus optional location/remote/experience
filters), and notifies (Telegram and/or email) about postings that
weren't seen on the previous run.

Run manually:

    python check_jobs.py

Designed to be run daily via GitHub Actions.
"""

import json
import re
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import yaml

from filters import filter_from_config
from keywords import matches_keywords
from notifications import notify_all
from providers import PROVIDERS


CONFIG_PATH = Path(__file__).parent / "config" / "companies.yaml"
STATE_PATH = Path(__file__).parent / "state.json"

MAX_WORKERS = 10


# ---------------------------------------------------------------------
# EXPERIENCE EXTRACTION
# ---------------------------------------------------------------------

EXPERIENCE_PATTERNS = [
    # Examples:
    # 3-5 years
    # 3–5 years
    # 3 to 5 years
    re.compile(
        r"\b(\d+(?:\.\d+)?)\s*(?:-|–|—|to)\s*(\d+(?:\.\d+)?)\s*"
        r"(?:years?|yrs?)\b",
        re.IGNORECASE,
    ),

    # Examples:
    # 3+ years
    # 3 or more years
    re.compile(
        r"\b(\d+(?:\.\d+)?)\s*\+\s*(?:years?|yrs?)\b",
        re.IGNORECASE,
    ),

    re.compile(
        r"\b(\d+(?:\.\d+)?)\s*(?:or\s+more)\s*(?:years?|yrs?)\b",
        re.IGNORECASE,
    ),

    # Examples:
    # minimum 3 years
    # minimum of 3 years
    re.compile(
        r"\bminimum(?:\s+of)?\s+(\d+(?:\.\d+)?)\s*"
        r"(?:years?|yrs?)\b",
        re.IGNORECASE,
    ),

    # Examples:
    # 3 years experience
    # 3 years of experience
    re.compile(
        r"\b(\d+(?:\.\d+)?)\s*(?:years?|yrs?)\s*"
        r"(?:of\s+)?experience\b",
        re.IGNORECASE,
    ),

    # Examples:
    # experience of 3 years
    re.compile(
        r"\bexperience\s+(?:of|:)\s*(\d+(?:\.\d+)?)\s*"
        r"(?:years?|yrs?)\b",
        re.IGNORECASE,
    ),
]


def extract_experience(text: str) -> str:
    """
    Extract the first useful experience requirement from a job posting.

    Examples:
        "3 years of experience" -> "3+ years"
        "3-5 years"             -> "3–5 years"
        "minimum 3 years"       -> "3+ years"
        "2 to 5 years"          -> "2–5 years"

    Returns:
        A normalized experience string, or "Not specified".
    """

    if not text:
        return "Not specified"

    # Normalize whitespace so patterns work better with scraped text.
    normalized = re.sub(r"\s+", " ", text).strip()

    for pattern in EXPERIENCE_PATTERNS:

        match = pattern.search(normalized)

        if not match:
            continue

        groups = match.groups()

        # Range: 3-5 years / 3 to 5 years
        if len(groups) >= 2 and groups[1] is not None:

            minimum = groups[0]
            maximum = groups[1]

            return f"{minimum}–{maximum} years"

        # Single minimum: 3+ years
        minimum = groups[0]

        return f"{minimum}+ years"

    return "Not specified"


def experience_match_label(experience: str) -> str:
    """
    Classify the job requirement against the user's ~3 years
    of experience.

    This does NOT filter jobs. It is only used for display.
    """

    if not experience or experience == "Not specified":
        return "⚪ Not specified"

    numbers = re.findall(
        r"\d+(?:\.\d+)?",
        experience
    )

    if not numbers:
        return "⚪ Not specified"

    values = [float(value) for value in numbers]

    minimum = values[0]
    maximum = values[1] if len(values) >= 2 else None

    target = 3.0

    # Range such as 2–5 years
    if maximum is not None:

        if minimum <= target <= maximum:
            return "🟢 Good match"

        if minimum <= target + 1:
            return "🟡 Possible"

        return "🔴 Above target"

    # Minimum requirement such as 3+ years
    if minimum <= target:
        return "🟢 Good match"

    if minimum <= target + 1:
        return "🟡 Possible"

    return "🔴 Above target"


def fetch_company_jobs(company: dict):
    """
    Runs in a worker thread: fetch + tag every job with the
    display name and configured priority tier.
    """

    name = company["name"]
    ctype = company["type"]
    value = company["value"]

    fetcher = PROVIDERS.get(ctype)

    if not fetcher:
        raise ValueError(
            f"Unknown provider type '{ctype}'"
        )

    jobs = fetcher(value)

    tier = company.get("tier", 2)

    for job in jobs:

        # Providers may set company to a slug/token.
        # Replace it with the friendly display name.
        job.company = name

        # Store company priority.
        job.tier = tier

        # Extract experience requirement from the posting.
        job.experience = extract_experience(
            f"{job.title}\n{job.description}"
        )

    return jobs


def load_state() -> dict:

    if STATE_PATH.exists():

        return json.loads(
            STATE_PATH.read_text()
        )

    return {}


def save_state(state: dict) -> None:

    STATE_PATH.write_text(
        json.dumps(
            state,
            indent=2,
            sort_keys=True
        )
    )


def main():

    if not CONFIG_PATH.exists():

        print(
            f"Missing config file: {CONFIG_PATH}",
            file=sys.stderr
        )

        sys.exit(1)

    config = yaml.safe_load(
        CONFIG_PATH.read_text()
    )

    companies = config.get(
        "companies",
        []
    )

    global_filter = filter_from_config(
        config.get("filters")
    )

    state = load_state()

    new_state = {}
    new_jobs_by_company = {}

    # Diagnostic counters
    total_fetched = 0
    total_keyword_matches = 0
    total_filter_matches = 0
    total_new = 0
    failed_companies = 0

    print("=" * 70)
    print("DOTNET JOB WATCHER")
    print("=" * 70)
    print(
        f"Companies configured: {len(companies)}"
    )
    print("=" * 70)

    with ThreadPoolExecutor(
        max_workers=MAX_WORKERS
    ) as pool:

        future_to_company = {
            pool.submit(
                fetch_company_jobs,
                company
            ): company
            for company in companies
        }

        for future in as_completed(
            future_to_company
        ):

            company = future_to_company[future]
            name = company["name"]

            try:

                jobs = future.result()

            except Exception as exc:

                failed_companies += 1

                print()
                print(f"✗ {name}")
                print(
                    f"  Failed to fetch: "
                    f"{type(exc).__name__}: {exc}"
                )

                # Keep previous state if provider fails.
                new_state[name] = state.get(
                    name,
                    []
                )

                continue

            fetched_count = len(jobs)

            total_fetched += fetched_count

            company_filter = (
                filter_from_config(
                    company["filters"]
                )
                if company.get("filters")
                else global_filter
            )

            # ---------------------------------------------------------
            # KEYWORD MATCHING
            # ---------------------------------------------------------

            keyword_matched_jobs = [
                job
                for job in jobs
                if matches_keywords(
                    f"{job.title}\n"
                    f"{job.description}"
                )
            ]

            keyword_match_count = len(
                keyword_matched_jobs
            )

            total_keyword_matches += (
                keyword_match_count
            )

            # ---------------------------------------------------------
            # FILTER MATCHING
            # ---------------------------------------------------------

            matched_jobs = [
                job
                for job in keyword_matched_jobs
                if company_filter.matches(job)
            ]

            filter_match_count = len(
                matched_jobs
            )

            total_filter_matches += (
                filter_match_count
            )

            # ---------------------------------------------------------
            # STATE / NEW JOB DETECTION
            # ---------------------------------------------------------

            previous_urls = set(
                state.get(name, [])
            )

            current_urls = {
                job.url
                for job in matched_jobs
            }

            new_urls = (
                current_urls - previous_urls
            )

            new_jobs = [
                job
                for job in matched_jobs
                if job.url in new_urls
            ]

            new_count = len(new_jobs)

            total_new += new_count

            if new_jobs:

                new_jobs_by_company[name] = (
                    new_jobs
                )

            new_state[name] = sorted(
                current_urls
            )

            # ---------------------------------------------------------
            # DIAGNOSTICS
            # ---------------------------------------------------------

            tier = company.get(
                "tier",
                2
            )

            tier_label = {
                1: "HIGH PRIORITY",
                2: "GOOD TARGET",
                3: "STRETCH",
            }.get(
                tier,
                "TARGET"
            )

            print()
            print(
                f"✓ {name} [{tier_label}]"
            )

            print(
                f"  Jobs fetched       : "
                f"{fetched_count}"
            )

            print(
                f"  Keyword matches    : "
                f"{keyword_match_count}"
            )

            print(
                f"  Filter matches     : "
                f"{filter_match_count}"
            )

            print(
                f"  Previously seen     : "
                f"{len(previous_urls)}"
            )

            print(
                f"  New matches        : "
                f"{new_count}"
            )

            if fetched_count == 0:

                print(
                    "  ⚠ Provider returned zero jobs."
                )

            elif keyword_match_count == 0:

                print(
                    "  ⚠ No jobs matched the "
                    "configured keywords."
                )

            elif filter_match_count == 0:

                print(
                    "  ⚠ Keyword matches were "
                    "removed by filters."
                )

    # -----------------------------------------------------------------
    # SAVE STATE
    # -----------------------------------------------------------------

    save_state(new_state)

    # -----------------------------------------------------------------
    # SUMMARY
    # -----------------------------------------------------------------

    print()
    print("=" * 70)
    print("RUN SUMMARY")
    print("=" * 70)

    print(
        f"Companies configured : "
        f"{len(companies)}"
    )

    print(
        f"Companies failed     : "
        f"{failed_companies}"
    )

    print(
        f"Jobs fetched         : "
        f"{total_fetched}"
    )

    print(
        f"Keyword matches      : "
        f"{total_keyword_matches}"
    )

    print(
        f"Filter matches       : "
        f"{total_filter_matches}"
    )

    print(
        f"New matches          : "
        f"{total_new}"
    )

    print("=" * 70)

    # -----------------------------------------------------------------
    # NOTIFICATIONS
    # -----------------------------------------------------------------

    if new_jobs_by_company:

        print(
            f"Sending notifications for "
            f"{total_new} new job(s)..."
        )

        notify_all(
            new_jobs_by_company
        )

    else:

        print(
            "No new matching jobs found."
        )


if __name__ == "__main__":
    main()