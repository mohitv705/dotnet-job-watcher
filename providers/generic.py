"""
Generic HTML career-page provider.

Scans server-rendered career/job listing pages for job links.

This provider is intentionally best-effort. It does not execute
JavaScript, so highly dynamic career portals may still require a
company-specific provider.
"""

import logging
import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from providers.base import Job
from providers.http import get

logger = logging.getLogger(__name__)

# Common URL patterns used by corporate career sites.
_JOB_URL_HINT = re.compile(
    r"(job|jobs|jobdetail|job-details|jobdetails|"
    r"jobdesc|jobapply|position|posting|opening|career)",
    re.IGNORECASE,
)

# Text that commonly indicates a real job title.
_JOB_TEXT_HINT = re.compile(
    r"(\.net|dotnet|c#|csharp|asp\.net|"
    r"software|developer|engineer|analyst|"
    r"consultant|programmer|application|"
    r"technology|technical|backend|back-end)",
    re.IGNORECASE,
)


def _clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def _looks_like_job_link(text: str, href: str) -> bool:
    """
    Decide whether an anchor is likely to represent a job posting.

    We deliberately allow more links than the previous provider because
    several enterprise career sites use URLs that don't contain the word
    'job'.
    """

    text = _clean_text(text)
    href = href or ""

    if not text or len(text) < 4:
        return False

    if _JOB_URL_HINT.search(href):
        return True

    if _JOB_TEXT_HINT.search(text):
        return True

    return False


def _extract_location(anchor) -> str:
    """
    Try to obtain a useful location from nearby HTML.

    This is best-effort because generic career pages have no consistent
    markup.
    """

    parent = anchor.parent

    if not parent:
        return ""

    text = _clean_text(
        parent.get_text(" ", strip=True)
    )

    # Keep this conservative. The company-specific providers should
    # handle structured location data where available.
    location_patterns = [
        r"\bBangalore\b",
        r"\bBengaluru\b",
        r"\bHyderabad\b",
        r"\bChennai\b",
        r"\bPune\b",
        r"\bMumbai\b",
        r"\bKolkata\b",
        r"\bGurugram\b",
        r"\bGurgaon\b",
        r"\bNoida\b",
        r"\bDelhi\b",
        r"\bIndia\b",
        r"\bRemote\b",
    ]

    locations = []

    for pattern in location_patterns:
        match = re.search(
            pattern,
            text,
            re.IGNORECASE,
        )

        if match:
            value = match.group(0)

            if value.lower() not in {
                item.lower()
                for item in locations
            }:
                locations.append(value)

    return ", ".join(locations)


def fetch(careers_url: str) -> list[Job]:
    """
    Fetch a server-rendered careers page and discover job links.

    The provider does NOT follow every discovered job page. It uses the
    listing/link text as the initial title and description because doing
    so keeps the generic provider lightweight.

    Company-specific providers should be used whenever a site exposes
    structured job APIs.
    """

    response = get(careers_url)

    soup = BeautifulSoup(
        response.text,
        "html.parser",
    )

    jobs = []
    seen_urls = set()

    for anchor in soup.find_all(
        "a",
        href=True,
    ):

        text = _clean_text(
            anchor.get_text(
                " ",
                strip=True,
            )
        )

        href = anchor.get("href", "")

        if not _looks_like_job_link(
            text,
            href,
        ):
            continue

        full_url = urljoin(
            careers_url,
            href,
        )

        if full_url in seen_urls:
            continue

        seen_urls.add(full_url)

        location = _extract_location(
            anchor
        )

        jobs.append(
            Job(
                title=text,
                url=full_url,
                location=location,
                company=careers_url,
                description=text,
            )
        )

    logger.info(
        "generic provider discovered %d candidate links for %s",
        len(jobs),
        careers_url,
    )

    return jobs