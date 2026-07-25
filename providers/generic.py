"""
Generic fallback provider. Scans a plain server-rendered careers page for
links whose visible text looks like a job posting and passes the base
keyword filter. Only works on static HTML — pages that render their job
list via JavaScript will return zero results (this is what icims.py and
successfactors.py fall back to, and both warn about the same limitation).

`value` in companies.yaml is the careers page URL.
"""

import logging
import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from keywords import matches_keywords
from providers.base import Job
from providers.http import get

logger = logging.getLogger(__name__)

_JOB_HINT = re.compile(r"(job|career|posting|position|role|opening)", re.IGNORECASE)


def fetch(careers_url: str) -> list[Job]:
    resp = get(careers_url)
    soup = BeautifulSoup(resp.text, "html.parser")

    jobs = []
    seen_urls = set()
    for a in soup.find_all("a", href=True):
        text = a.get_text(strip=True)
        href = a["href"]
        if not text or len(text) < 4:
            continue
        if not (_JOB_HINT.search(href) or _JOB_HINT.search(text)):
            continue
        if not matches_keywords(text):
            continue

        full_url = urljoin(careers_url, href)
        if full_url in seen_urls:
            continue
        seen_urls.add(full_url)

        jobs.append(Job(
            title=text,
            url=full_url,
            company=careers_url,
            description=text,
        ))

    if not jobs:
        logger.info("generic provider found 0 candidate links for %s", careers_url)

    return jobs
