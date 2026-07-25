"""
iCIMS provider — best effort.

Unlike Greenhouse/Lever/Ashby/SmartRecruiters, iCIMS has no single public
JSON API: each tenant's career site is configured differently, and many
render job search results via JavaScript, which plain HTML fetching can't
see at all. There is no way to genuinely guarantee this works across
iCIMS tenants without inspecting each one individually.

This provider currently reuses the generic HTML/keyword-link scan. If it
comes back empty for a company you know has open roles, open that
career page's browser devtools -> Network tab, reload the search, and
look for a JSON request the page itself makes (often something like
`/jobs/search` or `/graphql` returning job data) — point the "generic"
provider type at that JSON URL instead, or adapt this module once you've
confirmed the pattern for that tenant.

`value` in companies.yaml is the careers/search page URL.
"""

import logging

from providers.generic import fetch as generic_fetch

logger = logging.getLogger(__name__)


def fetch(careers_url: str) -> list:
    jobs = generic_fetch(careers_url)
    if not jobs:
        logger.info(
            "iCIMS provider found 0 matches for %s — this page may render "
            "results via JavaScript. See providers/icims.py for how to adapt.",
            careers_url,
        )
    return jobs
