from __future__ import annotations

import pytest

from pipdeptree._warning import WarningPrinter, WarningType, parse_warning_type


def test_warning_printer_print_single_line(capsys: pytest.CaptureFixture[str]) -> None:
    # Use WarningType.FAIL so that we can be able to test to see if WarningPrinter remembers it has warned before.
    warning_printer = WarningPrinter(WarningType.FAIL)
    warning_printer.print_single_line("test")
    assert warning_printer.has_warned_with_failure()
    out, err = capsys.readouterr()
    assert len(out) == 0
    assert err == "test\n"


@pytest.mark.parametrize(
    ("warning_type_str", "expected_warning_type"),
    [
        ("silence", WarningType.SILENCE),
        ("suppress", WarningType.SUPPRESS),
        ("fail", WarningType.FAIL),
        ("invalid-type", WarningType.SUPPRESS),
    ],
)
def test_parse_warning_type(warning_type_str: str, expected_warning_type: WarningType) -> None:
    actual_warning_type = parse_warning_type(warning_type_str)
    assert expected_warning_type == actual_warning_type
