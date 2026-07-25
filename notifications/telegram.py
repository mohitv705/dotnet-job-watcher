"""
Telegram notifier. Sends one message per batch of new matches, with each
job formatted as a small card (title/link, company, location, posted
date, remote/employment-type tags). Long batches are split across
multiple messages to stay under Telegram's ~4096 character limit.

Requires env vars: TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
"""

import os

from retry import retry_with_backoff
from providers.http import post as _http_post  # reuses the shared retrying HTTP helper

API_URL = "https://api.telegram.org/bot{token}/sendMessage"
MAX_MESSAGE_LEN = 4000  # margin under Telegram's 4096 hard limit


def _escape_html(text: str) -> str:
    return (text or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _format_job_block(job) -> str:
    title = _escape_html(job.title)
    company = _escape_html(job.company)
    location = _escape_html(job.location) if job.location else "Not specified"
    posted = _escape_html(job.posted_at) if job.posted_at else "Unknown"
    remote_tag = " \U0001F310 Remote" if job.remote else ""
    emp_type = f" \u00b7 {_escape_html(job.employment_type)}" if job.employment_type else ""

    return (
        f"\U0001F539 <a href=\"{job.url}\">{title}</a>\n"
        f"   \U0001F3E2 {company}{emp_type}\n"
        f"   \U0001F4CD {location}{remote_tag}\n"
        f"   \U0001F5D3 {posted}"
    )


def _chunk_message(header: str, blocks: list) -> list:
    chunks = []
    current = header
    for block in blocks:
        candidate = f"{current}\n\n{block}"
        if len(candidate) > MAX_MESSAGE_LEN:
            chunks.append(current)
            current = block
        else:
            current = candidate
    chunks.append(current)
    return chunks


def send(jobs_by_company: dict) -> bool:
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        return False

    blocks = []
    for jobs in jobs_by_company.values():
        for job in jobs:
            blocks.append(_format_job_block(job))

    total = sum(len(v) for v in jobs_by_company.values())
    header = f"<b>New .NET / backend job matches ({total})</b>"

    url = API_URL.format(token=token)
    for chunk in _chunk_message(header, blocks):
        _http_post(url, data={
            "chat_id": chat_id,
            "text": chunk,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        })

    return True
