from __future__ import annotations

import re


def pep503_normalize(name: str) -> str:
    return re.sub("[-_.]+", "-", name).lower()
