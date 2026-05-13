from datetime import date

import pytest

from nldate import parse
from nldate.parser import DateParseError


TODAY = date(2026, 5, 13)  # Wednesday


def test_today_tomorrow_and_yesterday() -> None:
    assert parse("today", TODAY) == TODAY
    assert parse("tomorrow", TODAY) == date(2026, 5, 14)
    assert parse("yesterday", TODAY) == date(2026, 5, 12)


def test_day_after_tomorrow() -> None:
    assert parse("the day after tomorrow", TODAY) == date(2026, 5, 15)


def test_numeric_relative_future() -> None:
    assert parse("in 3 days", TODAY) == date(2026, 5, 16)


def test_numeric_relative_past() -> None:
    assert parse("2 weeks ago", TODAY) == date(2026, 4, 29)


def test_word_number_relative() -> None:
    assert parse("two weeks from tomorrow", TODAY) == date(2026, 5, 28)


def test_duration_before_explicit_date() -> None:
    assert parse("5 days before December 1st, 2025", TODAY) == date(2025, 11, 26)


def test_multi_unit_duration_after_named_relative_date() -> None:
    assert parse("1 year and 2 months after yesterday", TODAY) == date(2027, 7, 12)


def test_next_weekday() -> None:
    assert parse("next Tuesday", TODAY) == date(2026, 5, 19)


def test_last_weekday() -> None:
    assert parse("last Friday", TODAY) == date(2026, 5, 8)


def test_bare_weekday_is_next_occurrence_including_today() -> None:
    assert parse("Wednesday", TODAY) == TODAY
    assert parse("Friday", TODAY) == date(2026, 5, 15)


def test_iso_date() -> None:
    assert parse("2025-12-01", TODAY) == date(2025, 12, 1)


def test_slash_date() -> None:
    assert parse("12/1/2025", TODAY) == date(2025, 12, 1)


def test_month_name_dates() -> None:
    assert parse("December 1st, 2025", TODAY) == date(2025, 12, 1)
    assert parse("1 Dec 25", TODAY) == date(2025, 12, 1)


def test_month_name_without_year_uses_current_year() -> None:
    assert parse("June 2", TODAY) == date(2026, 6, 2)


def test_month_and_year_clamp_end_of_month() -> None:
    assert parse("1 month after January 31, 2025", TODAY) == date(2025, 2, 28)


def test_next_month_and_year() -> None:
    assert parse("next month", TODAY) == date(2026, 6, 13)
    assert parse("next year", TODAY) == date(2027, 5, 13)


def test_end_of_month() -> None:
    assert parse("end of February 2024", TODAY) == date(2024, 2, 29)


def test_invalid_phrase_raises() -> None:
    with pytest.raises(DateParseError):
        parse("eventually maybe", TODAY)
