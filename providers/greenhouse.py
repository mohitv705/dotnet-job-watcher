"""
Greenhouse job board provider.

`value` in companies.yaml is the Greenhouse "board token" — find it in the
company's careers URL: boards.greenhouse.io/<TOKEN>
"""

from providers.base import Job
from providers.http import get


def fetch(board_token: str) -> list[Job]:
    url = f"https://boards-api.greenhouse.io/v1/boards/{board_token}/jobs?content=true"
    data = get(url).json()

    jobs = []
    for j in data.get("jobs", []):
        location = (j.get("location") or {}).get("name", "")
        jobs.append(Job(
            title=j.get("title", ""),
            url=j.get("absolute_url", ""),
            company=board_token,
            location=location,
            description=j.get("content", "") or "",
            posted_at=j.get("updated_at", "") or j.get("first_published", ""),
        ))
    return jobs
