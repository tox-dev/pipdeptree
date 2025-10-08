from __future__ import annotations

import pytest

from pipdeptree._warning import WarningPrinter, WarningType


@pytest.mark.parametrize(
    ("warning", "expected_type"),
    [
        ("silence", WarningType.SILENCE),
        ("suppress", WarningType.SUPPRESS),
        ("fail", WarningType.FAIL),
    ],
)
def test_warning_type_from_str_normal(warning: str, expected_type: WarningType) -> None:
    warning_type = WarningType.from_str(warning)
    assert expected_type == warning_type


def test_warning_type_from_str_invalid_warning() -> None:
    with pytest.raises(ValueError, match="Unknown WarningType string value provided"):
        WarningType.from_str("non-existent-warning-type")


def test_warning_printer_print_single_line(capsys: pytest.CaptureFixture[str]) -> None:
    # Use WarningType.FAIL so that we can be able to test to see if WarningPrinter remembers it has warned before.
    warning_printer = WarningPrinter(WarningType.FAIL)
    warning_printer.print_single_line("test")
    assert warning_printer.has_warned_with_failure()
    out, err = capsys.readouterr()
    assert len(out) == 0
    assert err == "test\n"
