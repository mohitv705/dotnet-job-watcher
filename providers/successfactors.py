"""
SAP SuccessFactors provider — best effort.

Same caveat as iCIMS (see providers/icims.py): SuccessFactors career sites
vary significantly per tenant and don't expose one universal public JSON
API the way Greenhouse/Lever/Ashby/SmartRecruiters do, and many render
results via JavaScript that plain HTML fetching won't see.

This provider currently reuses the generic HTML/keyword-link scan. If it
returns nothing for a company with known openings, check that career
page's Network tab in devtools for the JSON endpoint the page itself
calls, and adapt this module (or use "generic" pointed at that JSON URL
directly) once you've confirmed the pattern.

`value` in companies.yaml is the careers/search page URL.
"""

import logging

from providers.generic import fetch as generic_fetch

logger = logging.getLogger(__name__)


def fetch(careers_url: str) -> list:
    jobs = generic_fetch(careers_url)
    if not jobs:
        logger.info(
            "SuccessFactors provider found 0 matches for %s — this page may "
            "render results via JavaScript. See providers/successfactors.py "
            "for how to adapt.",
            careers_url,
        )
    return jobs
