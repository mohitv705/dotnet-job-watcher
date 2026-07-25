"""
Base keyword match applied to every job's title+description before any
location/remote/include-exclude filters in filters.py run. Edit
KEYWORD_PATTERN to widen or narrow what counts as a ".NET/C#/backend" role.
"""

import re

KEYWORD_PATTERN = re.compile(
    r"(\.net|dot\s?net|c#|c-sharp|csharp|asp\.net|backend|back-end|back\send)",
    re.IGNORECASE,
)


def matches_keywords(text: str) -> bool:
    return bool(KEYWORD_PATTERN.search(text or ""))
