"""A pragmatic natural-language date parser.

The parser intentionally handles a broad set of common English date phrases with
simple pattern matching instead of external services or machine learning.
"""

from __future__ import annotations

import calendar
import re
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Final


class DateParseError(ValueError):
    """Raised when a date phrase cannot be parsed."""


MONTHS: Final[dict[str, int]] = {
    "jan": 1,
    "january": 1,
    "feb": 2,
    "february": 2,
    "mar": 3,
    "march": 3,
    "apr": 4,
    "april": 4,
    "may": 5,
    "jun": 6,
    "june": 6,
    "jul": 7,
    "july": 7,
    "aug": 8,
    "august": 8,
    "sep": 9,
    "sept": 9,
    "september": 9,
    "oct": 10,
    "october": 10,
    "nov": 11,
    "november": 11,
    "dec": 12,
    "december": 12,
}

WEEKDAYS: Final[dict[str, int]] = {
    "monday": 0,
    "mon": 0,
    "tuesday": 1,
    "tue": 1,
    "tues": 1,
    "wednesday": 2,
    "wed": 2,
    "thursday": 3,
    "thu": 3,
    "thur": 3,
    "thurs": 3,
    "friday": 4,
    "fri": 4,
    "saturday": 5,
    "sat": 5,
    "sunday": 6,
    "sun": 6,
}

SMALL_NUMBERS: Final[dict[str, int]] = {
    "zero": 0,
    "a": 1,
    "an": 1,
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "eleven": 11,
    "twelve": 12,
    "thirteen": 13,
    "fourteen": 14,
    "fifteen": 15,
    "sixteen": 16,
    "seventeen": 17,
    "eighteen": 18,
    "nineteen": 19,
    "twenty": 20,
    "thirty": 30,
    "forty": 40,
    "fifty": 50,
    "sixty": 60,
    "seventy": 70,
    "eighty": 80,
    "ninety": 90,
}

ORDINALS: Final[dict[str, int]] = {
    "first": 1,
    "second": 2,
    "third": 3,
    "fourth": 4,
    "fifth": 5,
    "sixth": 6,
    "seventh": 7,
    "eighth": 8,
    "ninth": 9,
    "tenth": 10,
    "eleventh": 11,
    "twelfth": 12,
    "thirteenth": 13,
    "fourteenth": 14,
    "fifteenth": 15,
    "sixteenth": 16,
    "seventeenth": 17,
    "eighteenth": 18,
    "nineteenth": 19,
    "twentieth": 20,
    "twenty first": 21,
    "twenty second": 22,
    "twenty third": 23,
    "twenty fourth": 24,
    "twenty fifth": 25,
    "twenty sixth": 26,
    "twenty seventh": 27,
    "twenty eighth": 28,
    "twenty ninth": 29,
    "thirtieth": 30,
    "thirty first": 31,
}

TOKEN_REPLACEMENTS: Final[dict[str, str]] = {
    "couple": "2",
    "dozen": "12",
}


@dataclass(frozen=True)
class Duration:
    years: int = 0
    months: int = 0
    weeks: int = 0
    days: int = 0

    def __neg__(self) -> Duration:
        return Duration(
            years=-self.years,
            months=-self.months,
            weeks=-self.weeks,
            days=-self.days,
        )

    def apply(self, base: date) -> date:
        shifted = _add_months(base, self.years * 12 + self.months)
        return shifted + timedelta(weeks=self.weeks, days=self.days)

    @property
    def is_zero(self) -> bool:
        return self.years == self.months == self.weeks == self.days == 0


def parse(s: str, today: date | None = None) -> date:
    """Parse a common English date phrase into a ``datetime.date``.

    Args:
        s: A date phrase such as ``"next Tuesday"`` or
            ``"5 days before December 1st, 2025"``.
        today: Reference date for relative expressions. Defaults to the current
            local date.

    Raises:
        DateParseError: If the phrase is empty or unsupported.
    """

    reference = today if today is not None else date.today()
    if not isinstance(s, str):
        msg = "parse() expects a string"
        raise TypeError(msg)

    phrase = _normalize(s)
    if not phrase:
        msg = "cannot parse an empty date phrase"
        raise DateParseError(msg)

    return _parse_phrase(phrase, reference)


def _parse_phrase(phrase: str, today: date) -> date:
    phrase = _strip_outer_words(phrase)

    if phrase in {"today", "now"}:
        return today
    if phrase == "tomorrow":
        return today + timedelta(days=1)
    if phrase == "yesterday":
        return today - timedelta(days=1)
    if phrase in {"day after tomorrow", "the day after tomorrow"}:
        return today + timedelta(days=2)
    if phrase in {"day before yesterday", "the day before yesterday"}:
        return today - timedelta(days=2)

    composed = _parse_composed_duration(phrase, today)
    if composed is not None:
        return composed

    relative = _parse_simple_relative(phrase, today)
    if relative is not None:
        return relative

    weekday = _parse_weekday(phrase, today)
    if weekday is not None:
        return weekday

    special = _parse_special_month_phrase(phrase, today)
    if special is not None:
        return special

    explicit = _parse_explicit_date(phrase, today)
    if explicit is not None:
        return explicit

    duration = _parse_duration(phrase)
    if duration is not None:
        return duration.apply(today)

    msg = f"could not parse date phrase: {phrase!r}"
    raise DateParseError(msg)


def _normalize(s: str) -> str:
    lowered = s.strip().lower()
    lowered = lowered.replace("-", " ")
    lowered = re.sub(r"\b(\d+)(st|nd|rd|th)\b", r"\1", lowered)
    lowered = lowered.replace(",", " ")
    lowered = lowered.replace(".", " ")
    lowered = re.sub(r"\s+", " ", lowered)
    return lowered.strip()


def _strip_outer_words(phrase: str) -> str:
    phrase = re.sub(r"^(on|at|by)\s+", "", phrase)
    phrase = re.sub(r"^the\s+", "", phrase)
    return phrase.strip()


def _parse_composed_duration(phrase: str, today: date) -> date | None:
    for connector, sign in ((" before ", -1), (" after ", 1), (" from ", 1)):
        if connector not in phrase:
            continue
        left, right = phrase.split(connector, 1)
        duration = _parse_duration(left)
        if duration is None:
            continue
        base = today if right in {"now", "today"} else _parse_phrase(right, today)
        return duration.apply(base) if sign > 0 else (-duration).apply(base)
    return None


def _parse_simple_relative(phrase: str, today: date) -> date | None:
    if phrase.startswith("in "):
        duration = _parse_duration(phrase.removeprefix("in "))
        if duration is not None:
            return duration.apply(today)

    if phrase.endswith(" ago"):
        duration = _parse_duration(phrase.removesuffix(" ago"))
        if duration is not None:
            return (-duration).apply(today)

    match = re.fullmatch(r"(next|last|previous|this)\s+(\w+)", phrase)
    if match is None:
        return None

    direction, unit = match.groups()
    if unit in {"day", "days"}:
        days = {"next": 1, "last": -1, "previous": -1, "this": 0}[direction]
        return today + timedelta(days=days)
    if unit in {"week", "weeks"}:
        weeks = {"next": 1, "last": -1, "previous": -1, "this": 0}[direction]
        return today + timedelta(weeks=weeks)
    if unit in {"month", "months"}:
        months = {"next": 1, "last": -1, "previous": -1, "this": 0}[direction]
        return _add_months(today, months)
    if unit in {"year", "years"}:
        years = {"next": 1, "last": -1, "previous": -1, "this": 0}[direction]
        return _add_months(today, years * 12)
    return None


def _parse_weekday(phrase: str, today: date) -> date | None:
    match = re.fullmatch(r"(?:(next|last|previous|this)\s+)?(\w+)", phrase)
    if match is None:
        return None
    direction, weekday_name = match.groups()
    if weekday_name not in WEEKDAYS:
        return None

    target = WEEKDAYS[weekday_name]
    current = today.weekday()
    forward = (target - current) % 7

    if direction == "next":
        days = forward if forward != 0 else 7
    elif direction in {"last", "previous"}:
        backward = (current - target) % 7
        days = -(backward if backward != 0 else 7)
    elif direction == "this":
        days = target - current
    else:
        days = forward

    return today + timedelta(days=days)


def _parse_special_month_phrase(phrase: str, today: date) -> date | None:
    match = re.fullmatch(
        r"(beginning|start|middle|mid|end)(?:\s+of)?\s+(.+)", phrase
    )
    if match is None:
        return None

    position, rest = match.groups()
    base = _parse_phrase(rest, today)
    if position in {"beginning", "start"}:
        day = 1
    elif position in {"middle", "mid"}:
        day = 15
    else:
        day = calendar.monthrange(base.year, base.month)[1]
    return date(base.year, base.month, day)


def _parse_explicit_date(phrase: str, today: date) -> date | None:
    compact = phrase.replace(" ", "")
    if match := re.fullmatch(r"(\d{4})(\d{2})(\d{2})", compact):
        year_text, month_text, day_text = match.groups()
        return _safe_date(int(year_text), int(month_text), int(day_text))

    for pattern in (
        r"(\d{4})/(\d{1,2})/(\d{1,2})",
        r"(\d{4}) (\d{1,2}) (\d{1,2})",
    ):
        if match := re.fullmatch(pattern, phrase):
            year_text, month_text, day_text = match.groups()
            return _safe_date(int(year_text), int(month_text), int(day_text))

    for pattern in (
        r"(\d{1,2})/(\d{1,2})/(\d{2,4})",
        r"(\d{1,2}) (\d{1,2}) (\d{2,4})",
    ):
        if match := re.fullmatch(pattern, phrase):
            month_text, day_text, year_text = match.groups()
            return _safe_date(
                _expand_year(int(year_text)),
                int(month_text),
                int(day_text),
            )

    month_names = "|".join(sorted(MONTHS, key=len, reverse=True))
    if match := re.fullmatch(
        rf"(?:\w+\s+)?({month_names})\s+(\d{{1,2}})(?:\s+(\d{{2,4}}))?",
        phrase,
    ):
        month_name, day_text, year_text = match.groups()
        year = today.year if year_text is None else _expand_year(int(year_text))
        return _safe_date(year, MONTHS[month_name], int(day_text))

    if match := re.fullmatch(
        rf"(?:\w+\s+)?(\d{{1,2}})\s+({month_names})(?:\s+(\d{{2,4}}))?",
        phrase,
    ):
        day_text, month_name, year_text = match.groups()
        year = today.year if year_text is None else _expand_year(int(year_text))
        return _safe_date(year, MONTHS[month_name], int(day_text))

    if match := re.fullmatch(rf"({month_names})(?:\s+(\d{{2,4}}))?", phrase):
        month_name, year_text = match.groups()
        year = today.year if year_text is None else _expand_year(int(year_text))
        return date(year, MONTHS[month_name], 1)

    ordinal = _ordinal_to_number(phrase)
    if ordinal is not None:
        return date(today.year, today.month, ordinal)

    return None


def _parse_duration(text: str) -> Duration | None:
    cleaned = text.strip()
    if not cleaned:
        return None
    cleaned = cleaned.replace(" and ", " ")
    cleaned = cleaned.replace(",", " ")
    cleaned = re.sub(r"\s+", " ", cleaned)

    years = months = weeks = days = 0
    consumed: list[tuple[int, int]] = []
    pattern = re.compile(
        r"(?P<num>\d+|[a-z]+(?:\s+[a-z]+)?)\s+"
        r"(?P<unit>years?|yrs?|months?|mos?|weeks?|wks?|days?)"
    )

    for match in pattern.finditer(cleaned):
        amount = _number_to_int(match.group("num"))
        if amount is None:
            continue
        unit = match.group("unit")
        if unit.startswith(("year", "yr")):
            years += amount
        elif unit.startswith(("month", "mo")):
            months += amount
        elif unit.startswith(("week", "wk")):
            weeks += amount
        else:
            days += amount
        consumed.append(match.span())

    if not consumed:
        return None

    remainder = cleaned
    for start, end in reversed(consumed):
        remainder = f"{remainder[:start]} {remainder[end:]}"
    remainder = re.sub(r"\b(and|plus)\b", " ", remainder)
    remainder = re.sub(r"\s+", " ", remainder).strip()
    if remainder:
        return None

    duration = Duration(years=years, months=months, weeks=weeks, days=days)
    return None if duration.is_zero else duration


def _number_to_int(text: str) -> int | None:
    text = text.strip()
    if text.isdigit():
        return int(text)
    if text in TOKEN_REPLACEMENTS:
        text = TOKEN_REPLACEMENTS[text]
    if text.isdigit():
        return int(text)
    if text in SMALL_NUMBERS:
        return SMALL_NUMBERS[text]
    pieces = text.split()
    if len(pieces) == 2 and pieces[0] in SMALL_NUMBERS and pieces[1] in SMALL_NUMBERS:
        value = SMALL_NUMBERS[pieces[0]] + SMALL_NUMBERS[pieces[1]]
        return value if value > SMALL_NUMBERS[pieces[0]] else None
    return None


def _ordinal_to_number(text: str) -> int | None:
    if text.isdigit():
        number = int(text)
    else:
        number = ORDINALS.get(text)
    if number is None or not 1 <= number <= 31:
        return None
    return number


def _add_months(base: date, months: int) -> date:
    zero_indexed_month = base.month - 1 + months
    year = base.year + zero_indexed_month // 12
    month = zero_indexed_month % 12 + 1
    day = min(base.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def _safe_date(year: int, month: int, day: int) -> date:
    try:
        return date(year, month, day)
    except ValueError as error:
        msg = f"invalid date: {year:04d}-{month:02d}-{day:02d}"
        raise DateParseError(msg) from error


def _expand_year(year: int) -> int:
    if year >= 100:
        return year
    return 2000 + year if year < 70 else 1900 + year
