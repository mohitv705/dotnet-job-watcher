#!/usr/bin/env python3
"""
dotnet-job-watcher
------------------
Fetches jobs from configured company career sources, filters them for
.NET/C#/backend relevance, tracks previously seen jobs, and sends
notifications for newly discovered matches.

This version adds detailed diagnostics so provider/filter failures are
visible instead of making GitHub Actions appear successful when no jobs
were actually retrieved.
"""

from __future__ import annotations

import concurrent.futures
import sys
from dataclasses import dataclass
from typing import Iterable

from config import load_config
from filters import JobFilter
from notifier import notify
from providers import get_provider
from state import load_state, save_state


@dataclass
class CompanyResult:
    name: str
    success: bool
    fetched: int = 0
    keyword_matches: int = 0
    filter_matches: int = 0
    new_jobs: int = 0
    error: str | None = None


def fetch_company(
    company: dict,
    job_filter: JobFilter,
) -> tuple[CompanyResult, list]:
    """
    Fetch and filter jobs for a single company.

    Returns:
        CompanyResult: diagnostic information
        list: filtered matching jobs
    """
    name = company["name"]

    try:
        provider = get_provider(company)

        jobs = list(provider.fetch_jobs())

        result = CompanyResult(
            name=name,
            success=True,
            fetched=len(jobs),
        )

        keyword_matches = 0
        filtered_jobs = []

        for job in jobs:
            if job_filter.matches_keywords(job):
                keyword_matches += 1

                if job_filter.matches(job):
                    filtered_jobs.append(job)

        result.keyword_matches = keyword_matches
        result.filter_matches = len(filtered_jobs)

        return result, filtered_jobs

    except Exception as exc:
        return (
            CompanyResult(
                name=name,
                success=False,
                error=f"{type(exc).__name__}: {exc}",
            ),
            [],
        )


def print_result(result: CompanyResult) -> None:
    """Print a human-readable diagnostic summary."""

    if not result.success:
        print(f"\n✗ {result.name}")
        print(f"  ERROR: {result.error}")
        return

    print(f"\n✓ {result.name}")
    print(f"  Fetched jobs       : {result.fetched}")
    print(f"  Keyword matches    : {result.keyword_matches}")
    print(f"  Filter matches     : {result.filter_matches}")

    if result.fetched == 0:
        print("  ⚠ WARNING: provider returned ZERO jobs")

    elif result.keyword_matches == 0:
        print("  ⚠ WARNING: no jobs matched the configured keywords")

    elif result.filter_matches == 0:
        print("  ⚠ WARNING: keyword matches were removed by filters")


def main() -> int:
    config = load_config()

    companies = config["companies"]

    job_filter = JobFilter(
        keywords=config.get("keywords", []),
        locations=config.get("locations", []),
        excluded_keywords=config.get("excluded_keywords", []),
    )

    state = load_state()

    print("=" * 70)
    print(".NET JOB WATCHER")
    print("=" * 70)
    print(f"Companies configured : {len(companies)}")
    print(f"Keywords configured  : {len(job_filter.keywords)}")
    print(f"Locations configured : {len(job_filter.locations)}")
    print("=" * 70)

    company_results: list[CompanyResult] = []
    all_new_jobs = []

    # Keep provider fetching concurrent, as in the original architecture.
    with concurrent.futures.ThreadPoolExecutor(
        max_workers=min(10, max(1, len(companies)))
    ) as executor:

        future_map = {
            executor.submit(fetch_company, company, job_filter): company
            for company in companies
        }

        for future in concurrent.futures.as_completed(future_map):
            company = future_map[future]

            try:
                result, jobs = future.result()
            except Exception as exc:
                # Defensive fallback. fetch_company should already catch errors.
                result = CompanyResult(
                    name=company["name"],
                    success=False,
                    error=f"{type(exc).__name__}: {exc}",
                )
                jobs = []

            company_results.append(result)
            print_result(result)

            if not result.success:
                # Keep existing state for failed companies.
                state.setdefault(result.name, [])
                continue

            previous_urls = set(state.get(result.name, []))

            new_jobs = [
                job
                for job in jobs
                if job.url not in previous_urls
            ]

            result.new_jobs = len(new_jobs)

            if new_jobs:
                print(f"  New jobs           : {len(new_jobs)}")

            for job in new_jobs:
                all_new_jobs.append(job)

            # Update state with every successfully fetched matching job.
            state[result.name] = sorted(
                previous_urls | {job.url for job in jobs}
            )

    # Save state once, after all companies have been processed.
    save_state(state)

    print("\n" + "=" * 70)
    print("RUN SUMMARY")
    print("=" * 70)

    successful = [r for r in company_results if r.success]
    failed = [r for r in company_results if not r.success]

    total_fetched = sum(r.fetched for r in company_results)
    total_keyword = sum(r.keyword_matches for r in company_results)
    total_filtered = sum(r.filter_matches for r in company_results)

    print(f"Companies checked   : {len(company_results)}")
    print(f"Successful providers: {len(successful)}")
    print(f"Failed providers    : {len(failed)}")
    print(f"Jobs fetched        : {total_fetched}")
    print(f"Keyword matches     : {total_keyword}")
    print(f"Filter matches      : {total_filtered}")
    print(f"New jobs            : {len(all_new_jobs)}")

    if failed:
        print("\nFAILED PROVIDERS")
        print("-" * 70)

        for result in failed:
            print(f"- {result.name}: {result.error}")

    zero_job_companies = [
        r.name
        for r in successful
        if r.fetched == 0
    ]

    if zero_job_companies:
        print("\nZERO-JOB PROVIDERS")
        print("-" * 70)

        for name in zero_job_companies:
            print(f"- {name}")

    print("=" * 70)

    # Notify only newly discovered jobs.
    if all_new_jobs:
        try:
            notify(all_new_jobs)
            print(f"\nNotification sent for {len(all_new_jobs)} new job(s).")
        except Exception as exc:
            print(
                f"\nERROR: notification failed: "
                f"{type(exc).__name__}: {exc}",
                file=sys.stderr,
            )
            return 1
    else:
        print("\nNo new matching jobs found.")

    # Important:
    # We deliberately don't fail GitHub Actions merely because a provider
    # returned zero jobs. Some companies genuinely may have no matching jobs.
    #
    # Actual provider exceptions are reported clearly above.
    #
    # We'll tighten this behavior after seeing the diagnostic results.

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
