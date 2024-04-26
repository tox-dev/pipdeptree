from __future__ import annotations

import sys
from enum import Enum
from typing import Callable

WarningType = Enum("WarningType", ["SILENCE", "SUPPRESS", "FAIL"])


class WarningPrinter:
    """Handles printing warning logic. For multi-line warnings, it delegates most of its logic to the caller."""

    def __init__(self) -> None:
        self._warning_type = WarningType.SUPPRESS
        self._has_warned = False
        self._file = sys.stderr

    @property
    def warning_type(self) -> WarningType:
        return self._warning_type

    @warning_type.setter
    def warning_type(self, new_warning_type: WarningType) -> None:
        self._warning_type = new_warning_type

    def should_warn(self) -> bool:
        return self._warning_type != WarningType.SILENCE

    def has_warned_with_failure(self) -> bool:
        return self._has_warned and self.warning_type == WarningType.FAIL

    def print_single_line(self, line: str) -> None:
        self._has_warned = True
        print(line, file=sys.stderr)  # noqa: T201

    def print_multi_line(self, summary: str, print_func: Callable, ignore_fail: bool = False) -> None:  # noqa: FBT001, FBT002
        print(f"Warning!!! {summary}:", file=sys.stderr)  # noqa: T201

        print_func()

        if ignore_fail:
            print("NOTE: This warning isn't a failure warning.", file=sys.stderr)  # noqa: T201
        else:
            self._has_warned = True

        print("-" * 72, file=sys.stderr)  # noqa: T201


_shared_warning_printer = WarningPrinter()


def get_warning_printer() -> WarningPrinter:
    """Shared warning printer, representing a module-level singleton object."""
    return _shared_warning_printer


def parse_warning_type(type_str: str) -> WarningType:
    if type_str == "silence":
        return WarningType.SILENCE
    if type_str == "fail":
        return WarningType.FAIL

    # Either type_str == "suppress" or we were given an invalid string. For the latter case, our argparse configuration
    # shouldn't allow this to happen, but we'll go ahead and use this warning type since it is the default.
    return WarningType.SUPPRESS


__all__ = ["WarningPrinter", "get_warning_printer", "parse_warning_type"]
