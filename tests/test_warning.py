from __future__ import annotations

from typing import TYPE_CHECKING

from pipdeptree._warning import WarningPrinter, WarningType

if TYPE_CHECKING:
    import pytest


def test_warning_printer_print_single_line(capsys: pytest.CaptureFixture[str]) -> None:
    # Use WarningType.FAIL so that we can be able to test to see if WarningPrinter remembers it has warned before.
    warning_printer = WarningPrinter(WarningType.FAIL)
    warning_printer.print_single_line("test")
    assert warning_printer.has_warned_with_failure()
    out, err = capsys.readouterr()
    assert len(out) == 0
    assert err == "test\n"
