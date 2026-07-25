"""
Fans a batch of new job matches out to every notification channel that
has its required env vars set. A channel's `send()` returns False (and
does nothing) when it's not configured, so you can enable Telegram,
email, both, or neither without touching this file.
"""

import logging

from notifications import email, telegram

logger = logging.getLogger(__name__)

_CHANNELS = [telegram, email]


def notify_all(jobs_by_company: dict) -> None:
    if not jobs_by_company:
        logger.info("No new matches this run — skipping notifications.")
        return

    any_sent = False
    for channel in _CHANNELS:
        try:
            if channel.send(jobs_by_company):
                any_sent = True
        except Exception as exc:
            logger.warning("Notifier %s failed: %s", channel.__name__, exc)

    if not any_sent:
        logger.warning(
            "No notification channel is configured (or all failed) — "
            "see README.md for TELEGRAM_* / SMTP_* env vars."
        )
