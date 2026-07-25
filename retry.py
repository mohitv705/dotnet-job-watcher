"""
Generic retry-with-exponential-backoff decorator, used by every provider
and notifier that makes a network call, so transient failures (timeouts,
rate limits, flaky DNS, etc.) don't kill an entire run.
"""

import functools
import logging
import random
import time

logger = logging.getLogger(__name__)


def retry_with_backoff(max_retries=3, base_delay=1.0, max_delay=30.0, exceptions=(Exception,)):
    """
    Retries the decorated function on the given exception types, waiting
    base_delay * 2^attempt seconds between tries (capped at max_delay),
    plus a little random jitter so parallel calls don't all retry in lockstep.
    """

    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            attempt = 0
            while True:
                try:
                    return func(*args, **kwargs)
                except exceptions as exc:
                    attempt += 1
                    if attempt > max_retries:
                        logger.warning(
                            "Giving up on %s after %d attempt(s): %s",
                            func.__qualname__, attempt, exc,
                        )
                        raise
                    delay = min(max_delay, base_delay * (2 ** (attempt - 1)))
                    delay += random.uniform(0, delay * 0.1)
                    logger.info(
                        "Retrying %s (attempt %d/%d) in %.1fs after: %s",
                        func.__qualname__, attempt, max_retries, delay, exc,
                    )
                    time.sleep(delay)

        return wrapper

    return decorator
