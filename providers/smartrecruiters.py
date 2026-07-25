"""
SmartRecruiters provider (public postings API — no auth needed).

`value` in companies.yaml is the SmartRecruiters "company identifier",
visible in the company's careers URL: jobs.smartrecruiters.com/<IDENTIFIER>
"""

from providers.base import Job
from providers.http import get

PAGE_SIZE = 100
MAX_JOBS = 1000


def fetch(company_identifier: str) -> list[Job]:
    jobs = []
    offset = 0

    while offset < MAX_JOBS:
        url = (
            f"https://api.smartrecruiters.com/v1/companies/{company_identifier}"
            f"/postings?limit={PAGE_SIZE}&offset={offset}"
        )
        data = get(url).json()
        content = data.get("content", [])
        if not content:
            break

        for p in content:
            loc = p.get("location", {}) or {}
            location_str = ", ".join(filter(None, [loc.get("city"), loc.get("region"), loc.get("country")]))
            job_id = p.get("id", "")
            jobs.append(Job(
                title=p.get("name", ""),
                url=f"https://jobs.smartrecruiters.com/{company_identifier}/{job_id}",
                company=company_identifier,
                location=location_str,
                posted_at=p.get("releasedDate", ""),
                remote=bool(loc.get("remote")) if "remote" in loc else None,
            ))

        total = data.get("totalFound", 0)
        offset += PAGE_SIZE
        if offset >= total:
            break

    return jobs
