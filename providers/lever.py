"""
Lever job board provider (public postings API — no auth needed).

`value` in companies.yaml is the Lever company slug, visible in the
company's careers URL: jobs.lever.co/<SLUG>
"""

from providers.base import Job
from providers.http import get


def fetch(slug: str) -> list[Job]:
    url = f"https://api.lever.co/v0/postings/{slug}?mode=json"
    data = get(url).json()

    jobs = []
    for p in data:
        categories = p.get("categories", {}) or {}
        jobs.append(Job(
            title=p.get("text", ""),
            url=p.get("hostedUrl", "") or p.get("applyUrl", ""),
            company=slug,
            location=categories.get("location", ""),
            description=p.get("descriptionPlain", "") or p.get("description", "") or "",
            posted_at=str(p.get("createdAt", "")),
            employment_type=categories.get("commitment", ""),
        ))
    return jobs
