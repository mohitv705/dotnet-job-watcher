"""
Accenture India career-site provider.

Accenture's public career search page exposes links to individual
`/in-en/careers/jobdetails` pages. The listing page does not reliably put the
actual job title/description in the anchor text, so the generic provider can
find the links but cannot produce useful Job records for keyword matching.

This provider:
  1. searches Accenture's India career portal for C#/.NET terms;
  2. collects individual job-detail URLs;
  3. fetches each detail page;
  4. extracts the title, location and full job-page text.

`value` in companies.yaml is the Accenture India careers URL. The provider
builds the search URLs itself so the config stays simple.
"""

import html
import logging
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import parse_qs, urlencode, urljoin, urlparse

from bs4 import BeautifulSoup

from providers.base import Job
from providers.http import get

logger = logging.getLogger(__name__)

SEARCH_TERMS = (
    "C#",
    ".NET",
    "ASP.NET",
)

MAX_PAGES_PER_TERM = 3
DETAIL_WORKERS = 8

JOB_DETAIL_RE = re.compile(
    r"/in-en/careers/jobdetails\?[^\s\"']*id=",
    re.IGNORECASE,
)

LOCATION_RE = re.compile(
    r"\b(?:Bengaluru|Bangalore|Hyderabad|Pune|Mumbai|Chennai|"
    r"Kolkata|Gurugram|Gurgaon|Noida|New Delhi|Delhi|Coimbatore|"
    r"Ahmedabad|Jaipur|Indore|India)\b",
    re.IGNORECASE,
)


def _search_url(base_url: str, term: str, page: int) -> str:
    parsed = urlparse(base_url)

    query = {
        "jk": term,
        "sb": "1",
        "pg": str(page),
        "is_rj": "0",
    }

    return parsed._replace(
        path="/in-en/careers/jobsearch",
        query=urlencode(query),
    ).geturl()


def _extract_job_urls(search_html: str, page_url: str) -> set[str]:
    soup = BeautifulSoup(search_html, "html.parser")
    urls = set()

    for anchor in soup.find_all("a", href=True):
        href = html.unescape(anchor["href"])
        absolute = urljoin(page_url, href)

        if JOB_DETAIL_RE.search(absolute):
            urls.add(absolute)

    return urls


def _extract_location(text: str) -> str:
    matches = []

    for match in LOCATION_RE.finditer(text):
        value = match.group(0)

        if value.lower() not in {
            item.lower()
            for item in matches
        }:
            matches.append(value)

    return ", ".join(matches[:3])


def _extract_title(soup: BeautifulSoup, url: str) -> str:
    h1 = soup.find("h1")

    if h1:
        title = h1.get_text(" ", strip=True)

        if title:
            return title

    title_tag = soup.find("title")

    if title_tag:
        title = title_tag.get_text(" ", strip=True)

        title = re.sub(
            r"\s*\|\s*Accenture.*$",
            "",
            title,
            flags=re.IGNORECASE,
        )

        if title:
            return title

    parsed = urlparse(url)

    job_id = parse_qs(
        parsed.query
    ).get("id", [""])[0]

    return (
        f"Accenture Job {job_id}"
        if job_id
        else "Accenture Job"
    )


def _fetch_detail(url: str) -> Job | None:
    try:
        response = get(url)

    except Exception as exc:
        logger.warning(
            "Failed to fetch Accenture job detail %s: %s",
            url,
            exc,
        )
        return None

    soup = BeautifulSoup(
        response.text,
        "html.parser",
    )

    container = (
        soup.find("main")
        or soup.find("article")
        or soup.body
    )

    if not container:
        return None

    text = container.get_text(
        " ",
        strip=True,
    )

    text = re.sub(
        r"\s+",
        " ",
        text,
    ).strip()

    if not text:
        return None

    title = _extract_title(
        soup,
        url,
    )

    location = _extract_location(
        text
    )

    return Job(
        title=title,
        url=url,
        company="Accenture",
        location=location,
        description=text,
    )


def fetch(base_url: str) -> list[Job]:
    """
    Return Accenture India job-detail records
    for C#/.NET searches.
    """

    detail_urls: set[str] = set()

    for term in SEARCH_TERMS:

        for page in range(
            1,
            MAX_PAGES_PER_TERM + 1,
        ):

            url = _search_url(
                base_url,
                term,
                page,
            )

            try:
                response = get(url)

            except Exception as exc:
                logger.warning(
                    "Failed to fetch Accenture "
                    "search page %s: %s",
                    url,
                    exc,
                )
                continue

            found = _extract_job_urls(
                response.text,
                url,
            )

            before = len(
                detail_urls
            )

            detail_urls.update(
                found
            )

            logger.info(
                "Accenture search '%s' page %d: "
                "%d job links (%d new)",
                term,
                page,
                len(found),
                len(detail_urls) - before,
            )

            if not found:
                break

    if not detail_urls:

        logger.info(
            "Accenture provider found "
            "0 job-detail URLs"
        )

        return []

    jobs = []

    with ThreadPoolExecutor(
        max_workers=DETAIL_WORKERS
    ) as pool:

        futures = {
            pool.submit(
                _fetch_detail,
                url,
            ): url
            for url in sorted(
                detail_urls
            )
        }

        for future in as_completed(
            futures
        ):

            job = future.result()

            if job:
                jobs.append(job)

    unique = {}

    for job in jobs:
        unique[job.url] = job

    result = list(
        unique.values()
    )

    logger.info(
        "Accenture provider fetched "
        "%d job detail pages",
        len(result),
    )

    return result