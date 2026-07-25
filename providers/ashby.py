"""
Ashby provider (public job-board API — no auth needed).

`value` in companies.yaml is the Ashby job board name, visible in the
company's careers URL: jobs.ashbyhq.com/<BOARD_NAME>
"""

from providers.base import Job
from providers.http import get


def fetch(board_name: str) -> list[Job]:
    url = f"https://api.ashbyhq.com/posting-api/job-board/{board_name}"
    data = get(url).json()

    jobs = []
    for j in data.get("jobs", []):
        jobs.append(Job(
            title=j.get("title", ""),
            url=j.get("jobUrl", "") or j.get("applyUrl", ""),
            company=board_name,
            location=j.get("locationName", "") or j.get("location", ""),
            description=j.get("descriptionPlain", "") or "",
            posted_at=j.get("publishedAt", ""),
            remote=j.get("isRemote"),
            employment_type=j.get("employmentType", ""),
        ))
    return jobs
