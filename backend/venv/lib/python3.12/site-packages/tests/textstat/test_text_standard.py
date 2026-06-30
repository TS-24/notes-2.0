from __future__ import annotations

import pytest
from textstat import textstat
from ..backend import resources


@pytest.mark.parametrize(
    "text, float_output, expected",
    [
        (resources.EMPTY_STR, True, 1.0),
        (resources.EMPTY_STR, False, "0th and 1st grade"),
        (resources.EASY_TEXT, True, 4.0),
        (resources.EASY_TEXT, False, "3rd and 4th grade"),
        (resources.SHORT_TEXT, True, 2.0),
        (resources.SHORT_TEXT, False, "1st and 2nd grade"),
        (resources.PUNCT_TEXT, True, 6.0),
        (resources.PUNCT_TEXT, False, "5th and 6th grade"),
        (resources.LONG_TEXT, True, 11.0),
        (resources.LONG_TEXT, False, "10th and 11th grade"),
    ],
)
def test_text_standard(text: str, float_output: bool, expected: float | str) -> None:
    ts = type(textstat)()
    assert ts.text_standard(text, float_output) == expected


@pytest.mark.parametrize(
    "text, float_output, min_expected, max_expected",
    [
        # Very simple text should clamp to minimum (1.0 / "0th and 1st grade")
        (resources.VERY_SIMPLE_TEXT, True, 1.0, 1.0),
        (resources.VERY_SIMPLE_TEXT, False, "0th and 1st grade", "0th and 1st grade"),
        # Very complex text should clamp to maximum (18.0 / "17th and 18th grade")
        (resources.VERY_COMPLEX_TEXT, True, 18.0, 18.0),
        (
            resources.VERY_COMPLEX_TEXT,
            False,
            "17th and 18th grade",
            "17th and 18th grade",
        ),
    ],
)
def test_text_standard_bounds(
    text: str, float_output: bool, min_expected: float | str, max_expected: float | str
) -> None:
    """Test that text_standard clamps to sensible grade level bounds."""
    ts = type(textstat)()
    result = ts.text_standard(text, float_output)
    assert result == min_expected or result == max_expected
