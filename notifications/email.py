"""
Email notifier (plain SMTP + STARTTLS — works with Gmail app passwords,
most providers). Sends one email per run listing all new matches with
full job details.

Requires env vars: SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, NOTIFY_EMAIL_TO
"""

import os
import smtplib
from email.mime.text import MIMEText

from retry import retry_with_backoff


def _format_job_line(job) -> str:
    location = job.location or "Not specified"
    posted = job.posted_at or "Unknown"
    remote = " [Remote]" if job.remote else ""
    emp_type = f" [{job.employment_type}]" if job.employment_type else ""
    return (
        f"- {job.title}{remote}{emp_type}\n"
        f"  Company : {job.company}\n"
        f"  Location: {location}\n"
        f"  Posted  : {posted}\n"
        f"  Link    : {job.url}\n"
    )


def _build_body(jobs_by_company: dict) -> str:
    lines = ["New .NET / backend job matches:", ""]
    for company, jobs in jobs_by_company.items():
        lines.append(f"== {company} ==")
        for job in jobs:
            lines.append(_format_job_line(job))
        lines.append("")
    return "\n".join(lines)


@retry_with_backoff(max_retries=3, base_delay=2.0, exceptions=(OSError, smtplib.SMTPException))
def _send_smtp(host, port, user, password, to_addr, msg):
    with smtplib.SMTP(host, port, timeout=20) as server:
        server.starttls()
        server.login(user, password)
        server.sendmail(user, [to_addr], msg.as_string())


def send(jobs_by_company: dict) -> bool:
    host = os.environ.get("SMTP_HOST")
    port = os.environ.get("SMTP_PORT")
    user = os.environ.get("SMTP_USER")
    password = os.environ.get("SMTP_PASSWORD")
    to_addr = os.environ.get("NOTIFY_EMAIL_TO")
    if not all([host, port, user, password, to_addr]):
        return False

    total = sum(len(v) for v in jobs_by_company.values())
    body = _build_body(jobs_by_company)

    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = f"New .NET job matches ({total})"
    msg["From"] = user
    msg["To"] = to_addr

    _send_smtp(host, int(port), user, password, to_addr, msg)
    return True
