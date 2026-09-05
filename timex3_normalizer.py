# -*- coding: utf-8 -*-
"""
Turn Assamese temporal expressions into TIMEX3 attributes.

This module sits on top of `assamese_temporal_extract`, which finds *where* the
expressions are; here we decide *what they mean*:

    <TIMEX3 tid="t1" type="DATE" value="2026-08-16" temporalFunction="true"
            anchorTimeID="t0">১৬ আগষ্ট</TIMEX3>

The regex layer is imported as-is and never modified.

Two reference points are needed to resolve an expression, mirroring how the
corpus is annotated:

* ``dct``   - the document creation time (TIMEX3 ``t0``). Deictic expressions
              ("আজি", "যোৱা সোমবাৰে", "চলিত মাহত") resolve against this.
* ``focus`` - the last calendar date actually mentioned in the running text.
              Bare clock times ("পুৱা ৯ বজাত") attach to whatever date the
              sentence is talking about, not to the DCT. Defaults to ``dct``.

`annotate_document` walks a document and keeps ``focus`` up to date for you.

Usage
-----
    from timex3_normalizer import annotate_document, to_timex3
    import datetime

    for tx in annotate_document(text, dct=datetime.date(2026, 9, 4)):
        print(tx.tid, tx.type, tx.value, tx.expression)
"""

from __future__ import annotations

import datetime as _dt
import re
from dataclasses import dataclass, replace
from typing import List, Optional

from assamese_temporal_extract import extract, normalize

__all__ = ["Timex3", "to_timex3", "annotate_document", "tag_document"]


# ---------------------------------------------------------------------------
# lexicons
#
# These mirror the vocabulary of the extraction regexes but as *value* tables,
# which is a different job: the regexes decide what counts as an expression,
# these decide what each word contributes to the TIMEX3 value.
# ---------------------------------------------------------------------------

_DIGITS = str.maketrans("০১২৩৪৫৬৭৮৯", "0123456789")

MONTHS = {
    "জানুৱাৰী": 1, "ফেব্ৰুৱাৰী": 2, "মাৰ্চ": 3, "এপ্ৰিল": 4, "মে": 5, "জুন": 6,
    "জুলাই": 7, "আগষ্ট": 8, "ছেপ্টেম্বৰ": 9, "ছেপ্তেম্বৰ": 9, "ছেপ্টম্বৰ": 9,
    "অক্টোবৰ": 10, "নৱেম্বৰ": 11, "ডিচেম্বৰ": 12,
}

# ISO weekday numbers: Monday = 1 ... Sunday = 7
WEEKDAYS = {
    "সোমবাৰ": 1, "মঙলবাৰ": 2, "মঙ্গলবাৰ": 2, "বুধবাৰ": 3, "বৃহস্পতিবাৰ": 4,
    "শুক্ৰবাৰ": 5, "শনিবাৰ": 6, "দেওবাৰ": 7,
}

NUMBER_WORDS = {
    "এক": 1, "এ": 1, "দুই": 2, "দু": 2, "তিনি": 3, "চাৰি": 4, "পাঁচ": 5,
    "পাচ": 5, "ছয়": 6, "ছ": 6, "সাত": 7, "আঠ": 8, "নয়": 9, "ন": 9, "দহ": 10,
}

ORDINALS = {
    "প্ৰথম": 1, "দ্বিতীয": 2, "দ্বিতীয়": 2, "তৃতীয়": 3, "চতুৰ্থ": 4, "পঞ্চম": 5,
    "ষষ্ঠ": 6, "সপ্তম": 7, "অষ্টম": 8, "নৱম": 9, "দশম": 10,
}

# part-of-day word -> (TIMEX3 code, hours to add when an explicit clock hour
# is present, i.e. 12-hour to 24-hour conversion)
DAY_PARTS = {
    "ৰাতিপুৱা": ("MO", 0), "প্ৰত্যুষ": ("MO", 0), "পুৱা": ("MO", 0),
    "দুপৰীয়া": ("AF", 12), "আবেলি": ("AF", 12), "বিয়লি": ("AF", 12),
    "সন্ধিয়া": ("EV", 12), "নিশা": ("NI", 12), "ৰাতি": ("NI", 12),
}

# duration unit -> (ISO designator, multiplier); "T" prefix marks a time unit
UNITS = {
    "ছেকেণ্ড": ("TS", 1), "মিনিট": ("TM", 1), "ঘণ্টা": ("TH", 1),
    "দিন": ("D", 1), "সপ্তাহ": ("W", 1), "মাহ": ("M", 1),
    "বছৰ": ("Y", 1), "বৰ্ষ": ("Y", 1), "দশক": ("Y", 10), "শতিকা": ("Y", 100),
}

PAST_MARKERS = ("যোৱা", "বিগত", "গত")
FUTURE_MARKERS = ("অহা", "আগামী", "আহি থকা", "আহিলে")
PRESENT_MARKERS = ("চলিত", "এতিয়া", "বৰ্তমান", "আজি")
# the markers exactly as they appear when they stand alone before a date
BARE_MARKERS = frozenset(PAST_MARKERS + FUTURE_MARKERS + PRESENT_MARKERS + ("এই",))

APPROX_MARKERS = ("প্ৰায়",)
DEADLINE_MARKERS = ("লৈকে", "পৰ্যন্ত")

# "a few / several" - a real duration whose count is unknown, written PX<unit>
VAGUE_QUANTIFIERS = ("কিছু", "কেইবা", "কেইটামান")
VAGUE_QUANTITY_RE = re.compile(r"কেই\S*?মান")

# suffixes meaning "-long / throughout", which make a bare unit a duration
SPAN_SUFFIXES = ("জোৰা", "জুৰি", "ধৰি")

# phrases with no calculable value - they only place the event on the timeline
PRESENT_REF_WORDS = ("বৰ্তমান", "এতিয়াও", "আজিকালি", "সময়ছোৱা")
VAGUE_PERIOD_WORDS = ("বতৰ", "নিৰ্বাচন", "মাহবোৰ")

# fixed phrases that read as a deadline on their own ("within the coming
# week"). ON_OR_BEFORE is otherwise carried by words outside the expression,
# so it is not guessed - see _deadline_mod.
DEADLINE_IDIOMS = ("আহি থকা সপ্তাহৰ", "আহিলে সপ্তাহৰ")

# Postpositions that follow an expression and modify it. They sit outside the
# annotated span, so they are only consulted when the caller passes the
# following text (annotate_document does).
#
# Each entry is (mod, marker words, how many following words to look at). The
# window matters: "২০০০ চনৰ পাছত" ("after 2000") is AFTER, but in "যোৱা বছৰৰ
# খৰাংৰ পিছত" ("after last year's drought") the পিছত governs the drought, not
# the date, so only the immediately following word counts. "পৰা" ("from") is
# deliberately absent - it marks a start point and carries no mod.
CONTEXT_MODS = (
    ("AFTER", ("পিছত", "পাছত", "পাছৰ"), 1),
    ("ON_OR_BEFORE", ("ভিতৰত", "ভিতৰতে", "লৈকে", "পৰ্যন্ত"), 2),
)
# a DURATION already says "within N days" by itself, so it takes no mod here
CONTEXT_MOD_TYPES = ("DATE", "TIME")
CONTEXT_WINDOW = 24  # characters after the expression

_MONTHS_RE = "|".join(sorted(MONTHS, key=len, reverse=True))
_WEEKDAYS_RE = "|".join(sorted(WEEKDAYS, key=len, reverse=True))
_UNITS_RE = "|".join(sorted(UNITS, key=len, reverse=True))
_NUMWORDS_RE = "|".join(sorted(NUMBER_WORDS, key=len, reverse=True))
_ORDINALS_RE = "|".join(sorted(ORDINALS, key=len, reverse=True))
_NUM_RE = r"[০-৯0-9]+"


# ---------------------------------------------------------------------------
# TIMEX3 record
# ---------------------------------------------------------------------------


@dataclass
class Timex3:
    """One TIMEX3 annotation."""

    type: str  # DATE | TIME | DURATION | SET
    value: str
    mod: str = ""
    temporalFunction: bool = False
    anchorTimeID: str = ""
    beginPoint: str = ""   # DURATION running forward from the anchor
    endPoint: str = ""     # DURATION running back to the anchor
    freq: str = ""         # SET: how often it repeats
    expression: str = ""
    tid: str = ""
    start: int = -1
    end: int = -1
    # the calendar day this expression put the narrative on, which is what a
    # later bare clock time attaches to. Not a TIMEX3 attribute.
    anchor_date: Optional[_dt.date] = None

    def as_row(self) -> dict:
        """Flat dict, one key per TIMEX3 attribute used in the corpus."""
        return {
            "tid": self.tid,
            "type": self.type,
            "value": self.value,
            "temporalFunction": str(self.temporalFunction).lower(),
            "anchorTimeID": self.anchorTimeID,
            "beginPoint": self.beginPoint,
            "endPoint": self.endPoint,
            "freq": self.freq,
            "mod": self.mod,
            "functionInDocument": "",
            "expression": self.expression,
        }

    def as_tag(self) -> str:
        """The expression wrapped in a TIMEX3 element."""
        attrs = [f'tid="{self.tid}"', f'type="{self.type}"', f'value="{self.value}"',
                 f'temporalFunction="{str(self.temporalFunction).lower()}"']
        for name in ("anchorTimeID", "beginPoint", "endPoint", "freq", "mod"):
            value = getattr(self, name)
            if value:
                attrs.append(f'{name}="{value}"')
        return f"<TIMEX3 {' '.join(attrs)}>{self.expression}</TIMEX3>"


# ---------------------------------------------------------------------------
# parsed view of one expression
# ---------------------------------------------------------------------------


@dataclass
class _Parsed:
    """Everything the resolver needs to know about one expression."""

    text: str
    numbers: List[int]          # numeric quantities, in order
    unit: Optional[str]         # duration/calendar unit word
    month: Optional[int]
    weekday: Optional[int]
    day_part: Optional[str]     # part-of-day word
    hour: Optional[int]
    minute: Optional[int]
    second: Optional[int]
    year: Optional[int]
    day: Optional[int]
    ordinal: Optional[int]
    direction: int              # -1 past, +1 future, 0 present/none
    marker: str                 # the relative marker word that was found
    approx: bool
    deadline: bool
    vague: bool                 # "a few X" - a count that TIMEX3 writes as X
    span: bool                  # "-long / throughout X"

    def has(self, *words: str) -> bool:
        return any(w in self.text for w in words)


def _to_int(token: str) -> int:
    return int(token.translate(_DIGITS))


def _fix_doubled_marks(text: str) -> str:
    """Collapse a doubled vowel sign, e.g. the "দুুদিনৰ" typo in the corpus."""
    return re.sub(r"([়-্])\1+", r"\1", text)


def _parse(raw: str) -> _Parsed:
    """Pull every value-bearing feature out of a (normalized) expression."""
    text = _fix_doubled_marks(raw)
    numbers = [_to_int(m) for m in re.findall(_NUM_RE, text)]

    marker, direction = "", 0
    for words, sign in (
        (FUTURE_MARKERS, 1), (PAST_MARKERS, -1), (PRESENT_MARKERS, 0),
    ):
        for w in words:
            if w in text:
                marker, direction = w, sign
                break
        if marker:
            break

    # "অহা কালি" is tomorrow, not yesterday: the marker flips কালি's direction
    if "কালি" in text and "আজিকালি" not in text:
        direction = 1 if "অহা" in text else -1
        marker = marker or "কালি"

    unit = next((u for u in sorted(UNITS, key=len, reverse=True) if u in text), None)
    day_part = next(
        (d for d in sorted(DAY_PARTS, key=len, reverse=True) if d in text), None
    )
    ordinal = next(
        (n for w, n in sorted(ORDINALS.items(), key=lambda kv: -len(kv[0])) if w in text),
        None,
    )

    month_match = re.search(_MONTHS_RE, text)
    month = MONTHS[month_match.group()] if month_match else None
    weekday_match = re.search(_WEEKDAYS_RE, text)
    weekday = WEEKDAYS[weekday_match.group()] if weekday_match else None

    # clock: "৯ বজা", "১২ বাজি ২ মিনিট ১৩ ছেকেণ্ড"
    hour = minute = second = None
    clock = re.search(rf"({_NUM_RE})\s*(?:টা\s*)?(?:বজা|বাজি)", text)
    if clock:
        hour = _to_int(clock.group(1))
        m = re.search(rf"({_NUM_RE})\s*মিনিট", text)
        minute = _to_int(m.group(1)) if m else None
        s = re.search(rf"({_NUM_RE})\s*ছেকেণ্ড", text)
        second = _to_int(s.group(1)) if s else None

    # a 4-digit number is a year; "N চন" is a year even if shorter
    year = None
    y = re.search(rf"({_NUM_RE})\s*(?:চন|খ্ৰীষ্টাব্দ)", text) or re.search(
        r"(?<![০-৯0-9])([০-৯0-9]{4})(?![০-৯0-9])", text
    )
    if y:
        year = _to_int(y.group(1))

    # the day of a "<day> <month>" date, ignoring the year and the clock
    day = None
    if month is not None:
        dm = re.search(rf"({_NUM_RE})\s*(?:তাৰিখ\w*\s*)?(?:{_MONTHS_RE})", text)
        md = re.search(rf"(?:{_MONTHS_RE})['’]?\s+({_NUM_RE})", text)
        if dm and _to_int(dm.group(1)) <= 31:
            day = _to_int(dm.group(1))
        elif md and _to_int(md.group(1)) <= 31:
            day = _to_int(md.group(1))

    vague = bool(VAGUE_QUANTITY_RE.search(text)) or any(
        w in text for w in VAGUE_QUANTIFIERS
    )
    approx = vague or any(w in text for w in APPROX_MARKERS)
    deadline = any(w in text for w in DEADLINE_MARKERS)
    span = any(w in text for w in SPAN_SUFFIXES)

    return _Parsed(
        text=text, numbers=numbers, unit=unit, month=month, weekday=weekday,
        day_part=day_part, hour=hour, minute=minute, second=second, year=year,
        day=day, ordinal=ordinal, direction=direction, marker=marker,
        approx=approx, deadline=deadline, vague=vague, span=span,
    )


# ---------------------------------------------------------------------------
# calendar helpers
# ---------------------------------------------------------------------------


def _shift_months(date: _dt.date, months: int) -> _dt.date:
    total = date.year * 12 + (date.month - 1) + months
    return _dt.date(total // 12, total % 12 + 1, 1)


def _iso_week(date: _dt.date) -> str:
    year, week, _ = date.isocalendar()
    return f"{year}-W{week:02d}"


def _nearest_weekday(ref: _dt.date, weekday: int, direction: int) -> _dt.date:
    """The occurrence of `weekday` closest to `ref` in the given direction.

    Backwards (and with no direction at all) `ref` itself counts: a Monday
    report saying "যোৱা সোমবাৰে" means that same Monday.
    """
    if direction > 0:
        forward = (weekday - ref.isoweekday()) % 7
        return ref + _dt.timedelta(days=forward or 7)
    return ref - _dt.timedelta(days=(ref.isoweekday() - weekday) % 7)


def _quantity(p: _Parsed) -> Optional[int]:
    """The count in a duration phrase: a digit, a spelled-out number, or None
    for "a few / several", which TIMEX3 writes as X."""
    if p.vague:
        return None
    if p.numbers:
        return p.numbers[0]
    if p.unit:
        for word, value in sorted(NUMBER_WORDS.items(), key=lambda kv: -len(kv[0])):
            if word + p.unit in p.text:
                return value
    match = re.search(rf"({_NUMWORDS_RE})\s*(?:টা\s*)?(?:{_UNITS_RE})", p.text)
    return NUMBER_WORDS[match.group(1)] if match else None


def _duration_value(p: _Parsed) -> Optional[str]:
    if not p.unit:
        return None
    code, multiplier = UNITS[p.unit]
    count = _quantity(p)
    if count is None:
        amount = "X" if p.vague else str(multiplier)
    else:
        amount = str(count * multiplier)
    return f"PT{amount}{code[1]}" if code.startswith("T") else f"P{amount}{code}"


# ---------------------------------------------------------------------------
# resolution rules
#
# Each rule sees the parsed expression plus the two reference dates and either
# returns a Timex3 or None to pass. The first rule that answers wins, so they
# are ordered most-specific first.
# ---------------------------------------------------------------------------


def _rule_set(p: _Parsed, dct, focus) -> Optional[Timex3]:
    """Recurring times: "প্ৰতি শনিবাৰে", "বাৰ্ষিক", "প্ৰতিদিনে"."""
    # "সপ্তাহত অন্ততঃ ৩ দিন" - at least 3 days a week
    if "অন্ততঃ" in p.text:
        count = _quantity(p) or 1
        return Timex3("SET", "P1W", mod="EQUAL_OR_MORE", freq=f"{count}D")
    if "বাৰ্ষিক" in p.text or "বার্ষিক" in p.text:
        return Timex3("SET", "P1Y", freq="P1Y")
    if "প্ৰতি" not in p.text:
        return None
    if p.weekday is not None:
        return Timex3("SET", f"XXXX-WXX-{p.weekday}", freq="P1W")
    if p.unit:
        code, _ = UNITS[p.unit]
        return Timex3("SET", f"P1{code}", freq=f"P1{code}")
    return None


def _rule_reference(p: _Parsed, dct, focus) -> Optional[Timex3]:
    """Expressions that name a region of the timeline but no calculable date."""
    # "আজিলৈকে" / "এতিয়ালৈকে" / "এইপৰ্যন্ত" - up to and including today.
    # "আজি নিশালৈকে" names a time of day instead, so it is left to _rule_time.
    if (p.deadline and p.day_part is None and p.hour is None
            and p.has("আজি", "এতিয়া", "এইপৰ্যন্ত")):
        return Timex3("DATE", dct.isoformat(), mod="ON_OR_BEFORE",
                      temporalFunction=True, anchorTimeID="t0")
    # "যোৱা বৰ্ষৰ একেটা সময়ছোৱাত" ("the same period last year") names a real
    # year, so let the calendar rules have it
    if p.has(*PRESENT_REF_WORDS) and not (p.unit in ("বছৰ", "বৰ্ষ") and p.direction):
        return Timex3("DATE", "PRESENT_REF", temporalFunction=True, anchorTimeID="t0")
    if "ভৱিষ্যতে" in p.text:
        return Timex3("DATE", "FUTURE_REF", temporalFunction=True, anchorTimeID="t0")
    if p.has(*VAGUE_PERIOD_WORDS):
        value = "FUTURE_REF" if p.direction > 0 else "PAST_REF"
        return Timex3("DATE", value, temporalFunction=True, anchorTimeID="t0")
    return None


def _rule_century(p: _Parsed, dct, focus) -> Optional[Timex3]:
    """"অষ্টম-নৱম শতিকাতে" - the 8th century is the years 07XX."""
    if p.unit != "শতিকা" or p.ordinal is None:
        return None
    return Timex3("DATE", f"{p.ordinal - 1:02d}XX", mod="APPROX")


def _rule_quarter(p: _Parsed, dct, focus) -> Optional[Timex3]:
    """Financial-year quarters: FY Q1 (Apr-Jun) is calendar Q2."""
    if "ত্ৰৈমাসিক" not in p.text:
        return None
    quarter = (p.ordinal or 1) + 1
    year = dct.year + p.direction if p.marker in ("যোৱা", "গত") else dct.year
    return Timex3("DATE", f"{year}-Q{quarter}", temporalFunction=True, anchorTimeID="t0")


def _anchor_points(p: _Parsed) -> dict:
    """A directed duration is measured from ("আহি থকা ৭ দিনৰ") or up to
    ("বিগত ৭ দিনে") the document creation time."""
    if p.direction > 0:
        return {"beginPoint": "t0"}
    if p.direction < 0:
        return {"endPoint": "t0"}
    return {}


def _rule_vague_days(p: _Parsed, dct, focus) -> Optional[Timex3]:
    """"আহিলে বৰষুণৰ দিনবোৰত" - an unspecified number of days."""
    if "দিনবোৰ" not in p.text:
        return None
    return Timex3("DURATION", "PXD", mod="APPROX" if p.vague else "",
                  **_anchor_points(p))


def _rule_duration(p: _Parsed, dct, focus) -> Optional[Timex3]:
    """A length of time rather than a point on the calendar."""
    if p.unit is None or p.month is not None or p.hour is not None:
        return None
    if p.day_part is not None:
        return None

    counted = p.vague or _quantity(p) is not None
    # "বিগত সপ্তাহত" (the past week) is a length; "যোৱা সপ্তাহত" (last week) is
    # a calendar week. Only বিগত, a span suffix, or an explicit count turn a
    # bare unit into a duration - except "আহিলে মাহৰ", which the corpus also
    # reads as a length.
    if not counted and p.marker != "বিগত" and not p.span:
        if not (p.marker == "আহিলে" and p.unit == "মাহ"):
            return None

    value = _duration_value(p)
    return None if value is None else Timex3(
        "DURATION", value, mod="APPROX" if p.approx else "", **_anchor_points(p)
    )


def _rule_time(p: _Parsed, dct, focus) -> Optional[Timex3]:
    """A point in the day: a clock reading or a part-of-day word."""
    if p.hour is None and p.day_part is None:
        return None

    anchor = _date_for_time(p, dct, focus)
    date = anchor
    if p.hour is not None:
        hour = p.hour
        if p.day_part:
            _, offset = DAY_PARTS[p.day_part]
            if offset and hour < 12:
                hour += offset
            # midnight belongs to the next calendar day, but the narrative is
            # still on the day named before it, so `anchor` stays put
            if hour == 12 and DAY_PARTS[p.day_part][0] == "NI":
                hour, date = 0, date + _dt.timedelta(days=1)
        stamp = f"{hour:02d}:{p.minute or 0:02d}"
        if p.second is not None:
            stamp += f":{p.second:02d}"
        value = f"{date.isoformat()}T{stamp}"
    else:
        value = f"{date.isoformat()}T{DAY_PARTS[p.day_part][0]}"

    return Timex3("TIME", value, mod="APPROX" if p.approx else "",
                  temporalFunction=True, anchorTimeID="t0", anchor_date=anchor)


def _date_for_time(p: _Parsed, dct, focus) -> _dt.date:
    """Which day a clock time belongs to."""
    if p.month is not None and p.day is not None:
        return _dt.date(p.year or dct.year, p.month, p.day)
    if p.weekday is not None:
        return _nearest_weekday(dct, p.weekday, p.direction)
    if p.has("আজি", "এতিয়া"):
        return dct
    if "কালি" in p.text:
        return dct + _dt.timedelta(days=p.direction or -1)
    if "কাইলৈ" in p.text:
        return dct + _dt.timedelta(days=1)
    return focus


def _rule_absolute_date(p: _Parsed, dct, focus) -> Optional[Timex3]:
    """A date the expression states outright, in whole or in part."""
    explicit_year = p.year is not None
    anchored = not explicit_year

    # "গত বৰ্ষৰ ৮ ছেপ্টেম্বৰৰ" - a year word carries the date back a year
    year = p.year or dct.year
    if p.year is None and p.unit in ("বছৰ", "বৰ্ষ"):
        year += p.direction

    if p.month is not None and p.day is not None:
        value = _dt.date(year, p.month, p.day).isoformat()
    elif p.month is not None:
        value = f"{year}-{p.month:02d}"
    elif explicit_year:
        value = str(p.year)
    else:
        return None

    return Timex3(
        "DATE", value,
        mod=_deadline_mod(p),
        temporalFunction=anchored,
        anchorTimeID="t0" if anchored else "",
    )


def _rule_relative_date(p: _Parsed, dct, focus) -> Optional[Timex3]:
    """Dates counted off the document creation time."""
    value = None

    if p.weekday is not None:
        value = _nearest_weekday(dct, p.weekday, p.direction).isoformat()
    elif p.has("কাইলৈ"):
        value = (dct + _dt.timedelta(days=1)).isoformat()
    elif "কালি" in p.text:
        value = (dct + _dt.timedelta(days=p.direction or -1)).isoformat()
    elif p.has("আজি", "এতিয়া"):
        value = dct.isoformat()
    elif p.unit in ("বছৰ", "বৰ্ষ"):
        value = str(dct.year + p.direction)
    elif p.unit == "মাহ":
        value = _shift_months(dct, p.direction).strftime("%Y-%m")
    elif p.unit == "সপ্তাহ":
        value = _iso_week(dct + _dt.timedelta(weeks=p.direction))

    if value is None:
        return None
    return Timex3("DATE", value, mod=_deadline_mod(p),
                  temporalFunction=True, anchorTimeID="t0")


def _deadline_mod(p: _Parsed) -> str:
    """"...লৈকে / ...পৰ্যন্ত" ("up to") is the one deadline marker carried by
    the expression itself. ON_OR_BEFORE and AFTER otherwise come from words
    *around* the expression ("ভিতৰত" = within, "পৰা" = since), which are
    outside the annotated span, so they are not inferred here."""
    if p.deadline or any(idiom in p.text for idiom in DEADLINE_IDIOMS):
        return "ON_OR_BEFORE"
    return ""


_RULES = (
    _rule_set,
    _rule_reference,
    _rule_century,
    _rule_quarter,
    _rule_vague_days,
    _rule_duration,
    _rule_time,
    _rule_absolute_date,
    _rule_relative_date,
)


# ---------------------------------------------------------------------------
# public API
# ---------------------------------------------------------------------------


def to_timex3(
    expression: str,
    dct: _dt.date,
    focus: Optional[_dt.date] = None,
    tid: str = "",
    context_after: str = "",
) -> Timex3:
    """Resolve one expression into TIMEX3 attributes.

    `dct` is the document creation time (TIMEX3 t0); `focus` is the date the
    surrounding text is talking about, which is what a bare clock time attaches
    to. `context_after` is the text immediately following the expression: the
    postposition living there ("...ৰ ভিতৰত" = within, "...ৰ পৰা" = since) is
    what decides ON_OR_BEFORE and AFTER, and it falls outside the annotated
    span. Falls back to a DATE with an empty value if no rule applies.
    """
    text = normalize(expression).strip()
    parsed = _parse(text)
    focus = focus or dct

    result = None
    for rule in _RULES:
        result = rule(parsed, dct, focus)
        if result is not None:
            break
    if result is None:
        result = Timex3("DATE", "")

    if not result.mod and context_after:
        mod = _context_mod(context_after, result.type)
        if mod:
            result = replace(result, mod=mod)

    return replace(result, expression=expression.strip(), tid=tid)


def _context_mod(context_after: str, type_: str) -> str:
    """The mod carried by the postposition following the expression."""
    if type_ not in CONTEXT_MOD_TYPES:
        return ""
    words = normalize(context_after)[:CONTEXT_WINDOW].split()
    for mod, markers, window in CONTEXT_MODS:
        if any(marker in word for word in words[:window] for marker in markers):
            return mod
    return ""


def annotate_document(
    text: str, dct: _dt.date, start_tid: int = 1, keep_unresolved: bool = False
) -> List[Timex3]:
    """Find every temporal expression in `text` and resolve it.

    Walks the document in order, moving the focus date forward whenever an
    expression resolves to a full calendar date, so that a later "পুৱা ৯ বজাত"
    attaches to the date the text last mentioned.

    Spans the extractor offers but no rule can resolve are dropped: a bare
    "যোৱা" ("gone", also "last") or a stray number carries no time by itself.
    Pass `keep_unresolved=True` to see them anyway, e.g. when debugging the
    extraction patterns.
    """
    text = normalize(text)
    spans = _join_neighbours(text, extract(text), dct)

    results: List[Timex3] = []
    focus = dct
    for start, end in spans:
        tx = to_timex3(text[start:end], dct, focus,
                       context_after=text[end:end + CONTEXT_WINDOW])
        tx.start, tx.end = start, end
        if tx.value or keep_unresolved:
            results.append(tx)
            focus = _next_focus(tx, focus)

    for number, tx in enumerate(results, start=start_tid):
        tx.tid = f"t{number}"
    return results


def _join_neighbours(text, matches, dct) -> List[tuple]:
    """Join spans the extractor reports separately but TIMEX3 treats as one.

    The extractor breaks at whitespace, so "আজি পুৱাৰ ভাগত" ("this morning")
    and "অহা ১০ ছেপ্টেম্বৰ" ("the coming 10 September") arrive in two pieces.
    Only whitespace may separate the pieces being joined.
    """
    joined: List[tuple] = []
    for start, end, _matched, _cats in matches:
        if joined:
            previous_start, previous_end = joined[-1]
            if text[previous_end:start].isspace() and _should_join(
                text[previous_start:previous_end], text[start:end], dct
            ):
                joined[-1] = (previous_start, end)
                continue
        joined.append((start, end))
    return joined


def _should_join(left: str, right: str, dct: _dt.date) -> bool:
    left_tx = to_timex3(left, dct)
    # a relative marker on its own ("অহা", "আহি থকা") only means something
    # once it is attached to what follows it. It has to be the bare marker:
    # "অহাৰ" is the verb "of coming", not a time word.
    if not left_tx.value:
        return (normalize(left).strip() in BARE_MARKERS
                and bool(to_timex3(f"{left} {right}", dct).value))
    # a day plus the part of that day ("আজি" + "পুৱাৰ ভাগত")
    return (
        left_tx.type == "DATE"
        and re.fullmatch(r"\d{4}-\d{2}-\d{2}", left_tx.value) is not None
        and _parse(normalize(right)).day_part is not None
    )


def _next_focus(tx: Timex3, focus: _dt.date) -> _dt.date:
    """The date the narrative stands on after this expression."""
    if tx.anchor_date is not None:
        return tx.anchor_date
    if tx.type == "DATE" and re.fullmatch(r"\d{4}-\d{2}-\d{2}", tx.value):
        return _dt.date.fromisoformat(tx.value)
    return focus


def tag_document(text: str, dct: _dt.date) -> str:
    """Return `text` with every temporal expression wrapped in a TIMEX3 tag."""
    text = normalize(text)
    out, cursor = [], 0
    for tx in annotate_document(text, dct):
        out.append(text[cursor:tx.start])
        out.append(tx.as_tag())
        cursor = tx.end
    out.append(text[cursor:])
    return "".join(out)


if __name__ == "__main__":
    demo_dct = _dt.date(2026, 9, 4)
    demo = (
        "আজি পুৱা ৯ বজাত সভা আৰম্ভ হ'ব। যোৱা সোমবাৰে ৩ ছেপ্টেম্বৰ ২০২৬ত "
        "বিগত ৭ দিনে বৰষুণ হৈছে আৰু অহা মাহত প্ৰতি শনিবাৰে বন্ধ থাকিব।"
    )
    for tx in annotate_document(demo, demo_dct):
        print(f"{tx.tid:<4} {tx.type:<9} {tx.value:<20} {tx.mod:<13} {tx.expression}")
