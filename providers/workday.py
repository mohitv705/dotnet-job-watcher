"""
Workday job board provider (Workday CXS API — no auth needed, this is the
same endpoint the public career site's own search box calls).

`value` in companies.yaml is a mapping:
    tenant:   the Workday tenant name
    wd_host:  the Workday pod, e.g. "wd1", "wd3", "wd5"
    site:     the career site name (often "External" or a company-specific name)

All three are visible in a company's Workday careers URL, which looks like:
    https://<tenant>.<wd_host>.myworkdayjobs.com/<site>
"""

from providers.base import Job
from providers.http import post

PAGE_SIZE = 20
MAX_JOBS = 1000  # safety cap so a mis-set tenant can't loop forever


def fetch(value: dict) -> list[Job]:
    tenant = value["tenant"]
    wd_host = value["wd_host"]
    site = value["site"]
    api_url = f"https://{tenant}.{wd_host}.myworkdayjobs.com/wday/cxs/{tenant}/{site}/jobs"
    site_base = f"https://{tenant}.{wd_host}.myworkdayjobs.com/{site}"

    jobs = []
    offset = 0
    while offset < MAX_JOBS:
        payload = {"appliedFacets": {}, "limit": PAGE_SIZE, "offset": offset, "searchText": ""}
        data = post(api_url, json=payload).json()
        postings = data.get("jobPostings", [])
        if not postings:
            break

        for p in postings:
            jobs.append(Job(
                title=p.get("title", ""),
                url=site_base + p.get("externalPath", ""),
                company=tenant,
                location=p.get("locationsText", ""),
                posted_at=p.get("postedOn", ""),
            ))

        total = data.get("total", 0)
        offset += PAGE_SIZE
        if offset >= total:
            break

    return jobs
