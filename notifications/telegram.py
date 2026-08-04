"""
Telegram notifier.

Sends one message per batch of new matches, with each job formatted
as a small card containing title/link, company, location, experience,
posted date, remote/employment-type tags.

Requires env vars:
    TELEGRAM_BOT_TOKEN
    TELEGRAM_CHAT_ID
"""

import os
import re

from providers.http import post as _http_post


API_URL = (
    "https://api.telegram.org/bot{token}/sendMessage"
)

MAX_MESSAGE_LEN = 4000


TIER_INFO = {
    1: ("🔥", "HIGH PRIORITY"),
    2: ("🟡", "GOOD TARGET"),
    3: ("🟠", "STRETCH"),
}


def _escape_html(text: str) -> str:

    return (
        (text or "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def _tier_info(job):

    tier = getattr(
        job,
        "tier",
        2
    )

    return TIER_INFO.get(
        tier,
        ("🔹", "TARGET")
    )


def _experience_match_label(
    experience: str
) -> str:
    """
    Compare the job's experience requirement
    against approximately 3 years of experience.

    This is display-only and does not filter jobs.
    """

    if (
        not experience
        or experience == "Not specified"
    ):
        return "⚪ Not specified"

    numbers = re.findall(
        r"\d+(?:\.\d+)?",
        experience
    )

    if not numbers:
        return "⚪ Not specified"

    values = [
        float(value)
        for value in numbers
    ]

    minimum = values[0]

    maximum = (
        values[1]
        if len(values) >= 2
        else None
    )

    target = 3.0

    # Range such as 2–5 years
    if maximum is not None:

        if (
            minimum <= target
            <= maximum
        ):
            return "🟢 Good match"

        if minimum <= target + 1:
            return "🟡 Possible"

        return "🔴 Above target"

    # Minimum requirement such as 3+ years
    if minimum <= target:
        return "🟢 Good match"

    if minimum <= target + 1:
        return "🟡 Possible"

    return "🔴 Above target"


def _format_job_block(job) -> str:

    title = _escape_html(
        job.title
    )

    company = _escape_html(
        job.company
    )

    location = (
        _escape_html(job.location)
        if job.location
        else "Not specified"
    )

    posted = (
        _escape_html(job.posted_at)
        if job.posted_at
        else "Unknown"
    )

    experience = getattr(
        job,
        "experience",
        "Not specified"
    )

    experience = _escape_html(
        experience
    )

    experience_match = (
        _experience_match_label(
            experience
        )
    )

    tier_icon, tier_name = (
        _tier_info(job)
    )

    remote_tag = (
        " 🌐 Remote"
        if job.remote
        else ""
    )

    emp_type = (
        f" · {_escape_html(job.employment_type)}"
        if job.employment_type
        else ""
    )

    return (
        f"{tier_icon} <b>{tier_name}</b>\n"
        f"🔹 <a href=\"{job.url}\">{title}</a>\n"
        f"   🏢 {company}{emp_type}\n"
        f"   📍 {location}{remote_tag}\n"
        f"   💼 Experience: "
        f"{experience} "
        f"{experience_match}\n"
        f"   🗓 {posted}"
    )


def _chunk_message(
    header: str,
    blocks: list
) -> list:

    chunks = []

    current = header

    for block in blocks:

        candidate = (
            f"{current}\n\n{block}"
        )

        if len(candidate) > MAX_MESSAGE_LEN:

            chunks.append(current)

            current = block

        else:

            current = candidate

    chunks.append(current)

    return chunks


def send(
    jobs_by_company: dict
) -> bool:

    token = os.environ.get(
        "TELEGRAM_BOT_TOKEN"
    )

    chat_id = os.environ.get(
        "TELEGRAM_CHAT_ID"
    )

    if not token or not chat_id:
        return False

    blocks = []

    for jobs in (
        jobs_by_company.values()
    ):

        for job in jobs:

            blocks.append(
                _format_job_block(job)
            )

    total = sum(
        len(jobs)
        for jobs in jobs_by_company.values()
    )

    tier_counts = {
        1: 0,
        2: 0,
        3: 0,
    }

    for jobs in (
        jobs_by_company.values()
    ):

        for job in jobs:

            tier = getattr(
                job,
                "tier",
                2
            )

            if tier in tier_counts:
                tier_counts[tier] += 1

    header_lines = [
        "<b>"
        "New .NET / backend job matches "
        f"({total})"
        "</b>"
    ]

    if tier_counts[1]:

        header_lines.append(
            f"🔥 High Priority: "
            f"{tier_counts[1]}"
        )

    if tier_counts[2]:

        header_lines.append(
            f"🟡 Good Targets: "
            f"{tier_counts[2]}"
        )

    if tier_counts[3]:

        header_lines.append(
            f"🟠 Stretch: "
            f"{tier_counts[3]}"
        )

    header = "\n".join(
        header_lines
    )

    url = API_URL.format(
        token=token
    )

    for chunk in _chunk_message(
        header,
        blocks
    ):

        _http_post(
            url,
            data={
                "chat_id": chat_id,
                "text": chunk,
                "parse_mode": "HTML",
                "disable_web_page_preview": True,
            },
        )

    return True