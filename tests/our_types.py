from __future__ import annotations

from typing import Dict, List, Tuple

MockGraph = Dict[Tuple[str, str], List[Tuple[str, List[Tuple[str, str]]]]]

__all__ = [
    "MockGraph",
]
