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

Designed to be run daily via GitHub Actions (see .github/workflows/job-check.yml).
"""

import json
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


def fetch_company_jobs(company: dict):
    """Runs in a worker thread: fetch + tag every job with the display name."""
    name = company["name"]
    ctype = company["type"]
    value = company["value"]

    fetcher = PROVIDERS.get(ctype)
    if not fetcher:
        raise ValueError(f"Unknown provider type '{ctype}'")

    jobs = fetcher(value)
    for job in jobs:
        job.company = name  # providers set company=slug/token; use the friendly name instead
    return jobs


def load_state() -> dict:
    if STATE_PATH.exists():
        return json.loads(STATE_PATH.read_text())
    return {}


def save_state(state: dict) -> None:
    STATE_PATH.write_text(json.dumps(state, indent=2, sort_keys=True))


def main():
    if not CONFIG_PATH.exists():
        print(f"Missing config file: {CONFIG_PATH}", file=sys.stderr)
        sys.exit(1)

    config = yaml.safe_load(CONFIG_PATH.read_text())
    companies = config.get("companies", [])
    global_filter = filter_from_config(config.get("filters"))

    state = load_state()
    new_state = {}
    new_jobs_by_company = {}

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        future_to_company = {pool.submit(fetch_company_jobs, c): c for c in companies}

        for future in as_completed(future_to_company):
            company = future_to_company[future]
            name = company["name"]

            try:
                jobs = future.result()
            except Exception as exc:
                print(f"Failed to fetch {name}: {exc}", file=sys.stderr)
                new_state[name] = state.get(name, [])  # keep prior state so we don't lose track
                continue

            company_filter = (
                filter_from_config(company["filters"]) if company.get("filters") else global_filter
            )

            matched_jobs = [
                job for job in jobs
                if matches_keywords(f"{job.title}\n{job.description}") and company_filter.matches(job)
            ]

            previous_urls = set(state.get(name, []))
            current_urls = {job.url for job in matched_jobs}
            new_urls = current_urls - previous_urls

            if new_urls:
                new_jobs_by_company[name] = [job for job in matched_jobs if job.url in new_urls]

            new_state[name] = sorted(current_urls)

    save_state(new_state)
    notify_all(new_jobs_by_company)

    total_new = sum(len(v) for v in new_jobs_by_company.values())
    print(f"Done. {total_new} new match(es) across {len(companies)} companies.")


if __name__ == "__main__":
    main()
