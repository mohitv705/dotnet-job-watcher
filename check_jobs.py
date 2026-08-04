
#!/usr/bin/env python3

from pathlib import Path
import concurrent.futures
import sys
import yaml

from filters import filter_from_config
from keywords import matches_keywords
from notifier import notify_all
from providers import get_provider
from state import load_state, save_state


CONFIG_PATH = Path(__file__).parent / "config" / "companies.yaml"


def fetch_company(company):
    """
    Fetch jobs for one company.

    Returns:
        company_name, jobs, error
    """
    name = company["name"]

    try:
        provider = get_provider(company)
        jobs = list(provider.fetch_jobs())

        return name, jobs, None

    except Exception as exc:
        return name, [], exc


def main():
    config = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))

    companies = config.get("companies", [])
    global_filter = filter_from_config(config.get("filters", {}))

    state = load_state()

    print("=" * 70)
    print(".NET JOB WATCHER")
    print("=" * 70)
    print(f"Companies configured: {len(companies)}")
    print("=" * 70)

    all_new_jobs = []

    successful_companies = 0
    failed_companies = 0

    total_fetched = 0
    total_keyword_matches = 0
    total_filter_matches = 0
    total_new_jobs = 0

    results = []

    with concurrent.futures.ThreadPoolExecutor(
        max_workers=min(10, max(1, len(companies)))
    ) as executor:

        futures = {
            executor.submit(fetch_company, company): company
            for company in companies
        }

        for future in concurrent.futures.as_completed(futures):
            company = futures[future]

            try:
                name, jobs, error = future.result()

            except Exception as exc:
                name = company["name"]
                jobs = []
                error = exc

            # ---------------------------------------------------------
            # PROVIDER FAILURE
            # ---------------------------------------------------------
            if error is not None:
                failed_companies += 1

                print()
                print(f"✗ {name}")
                print(f"  Provider error: {type(error).__name__}: {error}")

                results.append(
                    {
                        "name": name,
                        "success": False,
                        "fetched": 0,
                        "keyword_matches": 0,
                        "filter_matches": 0,
                        "new_jobs": 0,
                    }
                )

                # Preserve existing state for a failed provider.
                state.setdefault(name, [])

                continue

            successful_companies += 1

            fetched_count = len(jobs)
            total_fetched += fetched_count

            # ---------------------------------------------------------
            # KEYWORD MATCHING
            # ---------------------------------------------------------
            keyword_matches = [
                job
                for job in jobs
                if matches_keywords(job)
            ]

            keyword_match_count = len(keyword_matches)
            total_keyword_matches += keyword_match_count

            # ---------------------------------------------------------
            # CONFIGURED FILTER
            # ---------------------------------------------------------
            filtered_jobs = [
                job
                for job in keyword_matches
                if global_filter.matches(job)
            ]

            filter_match_count = len(filtered_jobs)
            total_filter_matches += filter_match_count

            # ---------------------------------------------------------
            # STATE / NEW JOBS
            # ---------------------------------------------------------
            previous_urls = set(state.get(name, []))

            new_jobs = [
                job
                for job in filtered_jobs
                if job.url not in previous_urls
            ]

            new_job_count = len(new_jobs)
            total_new_jobs += new_job_count

            all_new_jobs.extend(new_jobs)

            # Update state only after successful provider execution.
            state[name] = sorted(
                previous_urls | {job.url for job in filtered_jobs}
            )

            # ---------------------------------------------------------
            # DIAGNOSTICS
            # ---------------------------------------------------------
            print()
            print(f"✓ {name}")
            print(f"  Jobs fetched       : {fetched_count}")
            print(f"  Keyword matches    : {keyword_match_count}")
            print(f"  Filter matches     : {filter_match_count}")
            print(f"  New matches        : {new_job_count}")

            if fetched_count == 0:
                print("  ⚠ WARNING: provider returned zero jobs")

            elif keyword_match_count == 0:
                print("  ⚠ WARNING: no jobs matched the configured keywords")

            elif filter_match_count == 0:
                print("  ⚠ WARNING: keyword matches were removed by filters")

            results.append(
                {
                    "name": name,
                    "success": True,
                    "fetched": fetched_count,
                    "keyword_matches": keyword_match_count,
                    "filter_matches": filter_match_count,
                    "new_jobs": new_job_count,
                }
            )

    # Save state after all providers have completed.
    save_state(state)

    # -------------------------------------------------------------
    # SUMMARY
    # -------------------------------------------------------------
    print()
    print("=" * 70)
    print("RUN SUMMARY")
    print("=" * 70)

    print(f"Companies configured : {len(companies)}")
    print(f"Successful providers : {successful_companies}")
    print(f"Failed providers     : {failed_companies}")
    print(f"Jobs fetched         : {total_fetched}")
    print(f"Keyword matches      : {total_keyword_matches}")
    print(f"Filter matches       : {total_filter_matches}")
    print(f"New jobs             : {total_new_jobs}")

    # -------------------------------------------------------------
    # FAILED PROVIDERS
    # -------------------------------------------------------------
    failed = [
        result
        for result in results
        if not result["success"]
    ]

    if failed:
        print()
        print("FAILED PROVIDERS")
        print("-" * 70)

        for result in failed:
            print(f"- {result['name']}")

    # -------------------------------------------------------------
    # ZERO JOB PROVIDERS
    # -------------------------------------------------------------
    zero_jobs = [
        result
        for result in results
        if result["success"] and result["fetched"] == 0
    ]

    if zero_jobs:
        print()
        print("PROVIDERS RETURNING ZERO JOBS")
        print("-" * 70)

        for result in zero_jobs:
            print(f"- {result['name']}")

    # -------------------------------------------------------------
    # KEYWORD FAILURE
    # -------------------------------------------------------------
    no_keywords = [
        result
        for result in results
        if (
            result["success"]
            and result["fetched"] > 0
            and result["keyword_matches"] == 0
        )
    ]

    if no_keywords:
        print()
        print("COMPANIES WITH NO KEYWORD MATCHES")
        print("-" * 70)

        for result in no_keywords:
            print(f"- {result['name']}")

    # -------------------------------------------------------------
    # FILTER FAILURE
    # -------------------------------------------------------------
    removed_by_filter = [
        result
        for result in results
        if (
            result["success"]
            and result["keyword_matches"] > 0
            and result["filter_matches"] == 0
        )
    ]

    if removed_by_filter:
        print()
        print("COMPANIES WHERE FILTERS REMOVED ALL MATCHES")
        print("-" * 70)

        for result in removed_by_filter:
            print(
                f"- {result['name']} "
                f"({result['keyword_matches']} keyword matches)"
            )

    print("=" * 70)

    # -------------------------------------------------------------
    # NOTIFICATIONS
    # -------------------------------------------------------------
    if all_new_jobs:
        try:
            notify_all(all_new_jobs)
            print(
                f"Notification sent for "
                f"{len(all_new_jobs)} new job(s)."
            )

        except Exception as exc:
            print(
                f"Notification failed: "
                f"{type(exc).__name__}: {exc}",
                file=sys.stderr,
            )
            return 1

    else:
        print("No new matching jobs found.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

