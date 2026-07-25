"""
Shared requests session with a sane User-Agent, timeout, and the project's
exponential-backoff retry decorator applied to every call. All providers
and the Telegram notifier import `get`/`post` from here instead of using
`requests` directly, so retry behavior is consistent everywhere.
"""

import requests

from retry import retry_with_backoff

TIMEOUT_SECONDS = 20

_session = requests.Session()
_session.headers.update({
    "User-Agent": "dotnet-job-watcher/1.0 (+https://github.com/)"
})


@retry_with_backoff(max_retries=3, base_delay=1.5, exceptions=(requests.RequestException,))
def get(url: str, **kwargs) -> requests.Response:
    resp = _session.get(url, timeout=TIMEOUT_SECONDS, **kwargs)
    resp.raise_for_status()
    return resp


@retry_with_backoff(max_retries=3, base_delay=1.5, exceptions=(requests.RequestException,))
def post(url: str, **kwargs) -> requests.Response:
    resp = _session.post(url, timeout=TIMEOUT_SECONDS, **kwargs)
    resp.raise_for_status()
    return resp
