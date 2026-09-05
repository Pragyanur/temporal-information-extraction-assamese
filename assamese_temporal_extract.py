# -*- coding: utf-8 -*-
"""
Assamese temporal-expression extraction — v3.

IMPORTANT: call `normalize()` on any text before matching (and this module
normalizes its own pattern source at import time), because the corpus mixes
precomposed and decomposed encodings of the same nukta letters (য়/ড়/ঢ়) -
e.g. two on-disk copies of the word "এতিয়াও" can be genuinely different
byte sequences that render identically. Without normalization, some
occurrences of an otherwise-listed word silently fail to match.

Three regexes, meant to be run together (finditer over the same text, spans
merged if adjacent/overlapping):

    TIME     - clock time            ("পুৱা ৯ বজাত", "নিশা ১২ বাজি ২ মিনিট ১৩ ছেকেণ্ডত")
    DATE     - calendar date         ("২৬ জুন", "১৯১৭ চনৰ", "যোৱা দেওবাৰে")
    DURATION - relative time/duration ("যোৱা তিনি বছৰ", "বিগত ৭ দিনে", "আহি থকা মাহত", "৭৭ বছৰীয়া")

DURATION is the category almost entirely missing from the original code -
words like যোৱা/অহা/বিগত/আহি থকা/প্ৰায়, spelled-out numbers (তিনি, পাঁচ, ছ...),
and bare duration nouns (বছৰ, মাহ, সপ্তাহ, দিন, ঘণ্টা, দশক, শতিকা...) were not
handled by TIME or DATE at all, and account for roughly half of the target
expressions in this corpus.

Two boundary fixes since v3, both measured against the annotated corpus and
both leaving the 416/416 expression-list coverage untouched (see MONTH_WORD
and DATE_MARK_TAIL below for the details):

  * "মে" (May) must carry its apostrophe, so it stops matching inside
    ordinary words such as "মেৰামতি" (repair) - 11 false hits removed.
  * "তাৰিখে" only joins a date when a weekday or part-of-day follows it,
    matching how the corpus draws the span - 12 boundary errors removed.
"""

import re
import unicodedata


def normalize(text: str) -> str:
    """Canonicalize Assamese/Bengali text so identical-looking words compare
    equal regardless of whether nukta letters (য়, ড়, ঢ়) were typed/stored
    as one precomposed codepoint or as base+nukta. Always call this on input
    text before matching."""
    return unicodedata.normalize("NFC", text)


def _p(pattern: str) -> "re.Pattern":
    """Compile a VERBOSE regex after normalizing the pattern source itself,
    so the module behaves the same no matter which byte-form the literals in
    this file happened to be saved with."""
    return re.compile(normalize(pattern), re.VERBOSE)


NUMBER = r"[০-৯0-9]+"

# generic trailing case/emphasis suffix that can follow almost any
# date/time/duration noun in Assamese
SUFFIX = (
    r"(?:তকৈ|লৈকে|জুৰি|ধৰি|জোৰা|মানত|বোৰত|ৰীয়া|ৰহে|ৰতে|েই|"
    r"েও|এও|তও|ৰও|তো|ৰো|ীয়া|লৈ|তে|ৰে|ও|ৰ|ত|এ|ে|ো|ই)?"
)

# not preceded by another Assamese/Bengali LETTER (vowel/consonant/vowel-sign)
# - stops a closed word (যোৱা, গত, বতৰ, জুন...) from being "found" as a
# false-positive substring in the middle of an unrelated longer word (e.g.
# "গত" inside "ভাগত"). Bengali DIGITS (০-৯) are deliberately excluded from
# the blocked range, because day numbers legitimately sit glued directly
# against a month name with no space ("৩১আগষ্ট"). Don't put this on UNIT,
# which legitimately gets glued directly onto a preceding number-word with
# no space either ("তিনিমাহ", "ছবছৰ").
BSTART = r"(?<![ঀ-৥ৰ-৿])"

# a connector between two date components that may carry a bare possessive
# suffix and/or a comma, e.g. "২০২৬ৰ ৩০ এপ্ৰিলত", "৩১আগষ্ট , ২০২৬ত"
SEP = r"(?:ৰ|ৰে)?\s*,?\s*"
SEP1 = r"(?:ৰ|ৰে)?\s*,?\s+"  # same, but requires at least one whitespace

# ---------------------------------------------------------------------------
# TIME
# ---------------------------------------------------------------------------

PART_OF_DAY = r"(?:(?:গভীৰ\s+)?(?:পুৱা|ৰাতিপুৱা|দুপৰীয়া|বিয়লি|আবেলি|সন্ধিয়া|ৰাতি|নিশা|প্ৰত্যুষ))"

APPROX = r"(?:প্ৰায়|প্ৰায়েই)\s+"

HOUR = rf"{NUMBER}\s*(?:বজা|টা বজা|টা বাজি|বাজি)"
MINUTE = rf"{NUMBER}\s*মিনিট"
SECOND = rf"{NUMBER}\s*ছেকেণ্ড"

_TIME_CORE = rf"""
    (?:
        {PART_OF_DAY}\s+(?:{APPROX})?{HOUR}\s+{MINUTE}\s+{SECOND}
        |
        {PART_OF_DAY}\s+(?:{APPROX})?{HOUR}\s+{MINUTE}
        |
        {HOUR}\s+{MINUTE}\s+{SECOND}
        |
        {PART_OF_DAY}\s+(?:{APPROX})?{HOUR}
        |
        {HOUR}\s+{MINUTE}
        |
        {HOUR}\s+{SECOND}
        |
        {PART_OF_DAY}\s+{MINUTE}
        |
        {PART_OF_DAY}\s+{SECOND}
        |
        {PART_OF_DAY}
        |
        {HOUR}
        |
        {MINUTE}
        |
        {SECOND}
    )
"""

_TIME_CORE2 = rf"""
    (?:
        # longer/more specific alternatives must come before the shorter
        # ones they contain a prefix of (e.g. bare PART_OF_DAY), otherwise
        # the shorter one matches first and the longer tail is never tried
        {PART_OF_DAY}\s*ৰ?\s*ভাগত
        |
        {APPROX}{PART_OF_DAY}\s+(?:{APPROX})?{HOUR}
        |
        {_TIME_CORE}
    )
"""

TIME = _p(rf"{_TIME_CORE2}{SUFFIX}")

# ---------------------------------------------------------------------------
# DATE
# ---------------------------------------------------------------------------

DAY = rf"{NUMBER}\s*(?:তাৰিখ)?"
DAY_MARK = r"(?:তাৰিখ)"
# "মে" keeps its apostrophe on purpose: bare "মে" also opens ordinary words
# like "মেৰামতি" (repair), and the ৰ in the suffix lookahead below would let
# it match there
MONTH_WORD = rf"{BSTART}(?:জানুৱাৰী|ফেব্ৰুৱাৰী|মাৰ্চ|এপ্ৰিল|মে['’]|জুন|জুলাই|আগষ্ট|ছেপ্টেম্বৰ|ছেপ্তেম্বৰ|ছেপ্টম্বৰ|অক্টোবৰ|নৱেম্বৰ|ডিচেম্বৰ)"
_MONTH_LOOKAHEAD = r"ৰ|ত|লৈ|লৈকে|ৰে|তে|['’]|$|\s|[।,!?;:]"
MONTH = rf"{MONTH_WORD}(?={_MONTH_LOOKAHEAD})"
# longest alternatives first: "চনত" is a prefix of "চনতে", so if the shorter
# one is tried first the regex commits to it and never backtracks to try the
# longer one when nothing downstream forces a retry (finditer doesn't require
# consuming the whole string) - this bit everywhere a word-list has one
# member that is a prefix of another, so all such lists here are longest-first
YEAR_MARK = r"(?:চনতে|চনৰে|চনৰহে|চনৰো|চনৰ|চনত|চন|খ্ৰীষ্টাব্দত|খ্ৰীষ্টাব্দ)"
YEAR = rf"{NUMBER}\s*(?:{YEAR_MARK})?"
YEAR_STRICT = rf"{NUMBER}\s*{YEAR_MARK}"  # marker required - disambiguates from a bare DAY number
BARE_YEAR = rf"(?<!\S){NUMBER}(?!\S)"
NUMBER4 = r"[০-৯0-9]{4}"  # a lone 4-digit number with a plain case suffix, e.g. "২০২৬ৰ", "১৯৯০"
WEEKDAY = rf"{BSTART}(?:দেওবাৰ|সোমবাৰ|মঙলবাৰ|মঙ্গলবাৰ|বুধবাৰ|বৃহস্পতিবাৰ|শুক্ৰবাৰ|শনিবাৰ)"
WEEKDAY_SUF = rf"{WEEKDAY}{SUFFIX}(?:\s+{PART_OF_DAY})?"

# "২৪ মে' তাৰিখে নিশা" / "২৬ জুন তাৰিখে মঙ্গলবাৰৰে" - "তাৰিখে" ("on the
# date") is only part of the expression when a weekday or a part of the day
# follows it; on its own it is just the postposition after the date
DATE_MARK_TAIL = rf"(?:\s+তাৰিখে(?:\s+{WEEKDAY}{SUFFIX}|\s+{PART_OF_DAY}))?"

# month name used as "<month> মাহত/মাহৰ" ("জুলাই মাহত", "অহা ছেপ্টেম্বৰ মাহত")
MONTH_NOUN = rf"{MONTH}\s+মাহ{SUFFIX}"

DATE = _p(
    rf"""
    (?:
        {DAY}{SEP}{MONTH}{SEP1}{YEAR}{DATE_MARK_TAIL}
        |
        {YEAR}{SEP1}{DAY}{SEP}{MONTH}{DATE_MARK_TAIL}
        |
        {YEAR}{SEP1}{MONTH}{SEP1}{DAY}{DATE_MARK_TAIL}
        |
        {DAY}{SEP}{MONTH}{DATE_MARK_TAIL}
        |
        {MONTH}{SEP1}{DAY}
        |
        {MONTH_NOUN}
        |
        {MONTH}{SEP1}{YEAR_STRICT}
        |
        {YEAR_STRICT}{SEP1}{MONTH}
        |
        {DAY}\s+{DAY_MARK}
        |
        {WEEKDAY_SUF}
        |
        {MONTH}
        |
        {NUMBER}\s*{YEAR_MARK}
        |
        {NUMBER4}
        |
        {BARE_YEAR}
    )
    """
    rf"{SUFFIX}"
)

# ---------------------------------------------------------------------------
# DURATION / RELATIVE  (the category missing from the original code)
# ---------------------------------------------------------------------------

REL_PAST = r"(?:যোৱা|বিগত|গত)"
REL_FUTURE = r"(?:অহা|আগামী|আহি\s+থকা|আহিলে)"
REL_NOW = r"(?:এতিয়া|বৰ্তমান|চলিত|আজিকালি|আজি|কালি|কাইলৈ)"
REL_DEM = r"(?:এই)"
# NOTE: REL_MARK includes the demonstrative "এই" ("this"), which is only
# safe to treat as a time-relative marker when it is glued to a duration/unit
# noun ("এই বছৰ" = "this year", "এই তিনিটা দিন" = "these three days"). "এই"
# alone is an extremely common general-purpose demonstrative ("এই প্ৰবন্ধ" =
# "this article") - REL_MARK_BARE below deliberately excludes it so the
# "marker with no following noun" fallback doesn't fire on every "এই" in
# running text.
REL_MARK = rf"{BSTART}(?:{REL_PAST}|{REL_FUTURE}|{REL_NOW}|{REL_DEM})"
REL_MARK_BARE = rf"{BSTART}(?:{REL_PAST}|{REL_FUTURE}|{REL_NOW})"

APPROX_MARK = rf"{BSTART}(?:প্ৰায়|দীৰ্ঘ|অন্ততঃ|কিছু|কেইটামান|কেইবা)"

NUMBER_WORD = rf"{BSTART}(?:এক|দুই|তিনি|চাৰি|পাঁচ|পাচ|ছয়|সাত|আঠ|নয়|দহ|এ|দু|ছ|ন)"
CLASSIFIER = r"(?:\s*টা)?"
QUANT = rf"(?:{NUMBER}|{NUMBER_WORD}){CLASSIFIER}"

UNIT = r"(?:দিন|মাহ|বছৰ|সপ্তাহ|ঘণ্টা|মিনিট|ছেকেণ্ড|দশক|শতিকা|বৰ্ষ|যুগ|ত্ৰৈমাসিক|সময়ছোৱা)"
# "কেইদিনমান", "কেইমাহমান", "কেইবছৰমান", "কেইসপ্তাহমান" - fused approx-quantity+unit
FUSED_APPROX_UNIT = rf"কেই{UNIT}মান"

EVENT_NOUN = rf"{BSTART}(?:নিৰ্বাচন)"
SEASON = r"(?:ৰবি\s+শস্যৰ|বৰষুণৰ|শুকান)\s+(?:বতৰ|দিনবোৰ)"
PERIOD_NOUN = r"(?:একেটা\s+)?সময়ছোৱা"

ORDINAL = rf"{BSTART}(?:প্ৰথম|দ্বিতীয়|তৃতীয়|চতুৰ্থ|পঞ্চম|ষষ্ঠ|সপ্তম|অষ্টম|নৱম|দশম)"

DURATION = _p(
    rf"""
    (?:
        # fixed multi-word/compound phrases go first, so a shorter generic
        # alternative below (e.g. bare REL_DEM "এই") doesn't win first and
        # stop the match short
        এইপৰ্যন্ত|বাৰ্ষিক|ভৱিষ্যতে
        |
        # ordinal century / quarter / half-year, e.g. "অষ্টম-নৱম শতিকাতে", "প্ৰথম ত্ৰৈমাসিকত"
        {ORDINAL}(?:\s*-\s*{ORDINAL})?\s+(?:শতিকা|ত্ৰৈমাসিক|ছমাহ){SUFFIX}
        |
        # relative marker + descriptive season phrase ("আহি থকা ৰবি শস্যৰ বতৰত")
        {REL_MARK}\s+{SEASON}{SUFFIX}
        |
        # "সপ্তাহত অন্ততঃ ৩ দিন" - frequency-within-period
        {UNIT}{SUFFIX}\s+অন্ততঃ\s+{QUANT}\s*{UNIT}{SUFFIX}
        |
        # relative marker + year-phrase + a period noun ("যোৱা বৰ্ষৰ একেটা সময়ছোৱাত")
        {REL_MARK}\s*{UNIT}{SUFFIX}\s+{PERIOD_NOUN}{SUFFIX}
        |
        # relative marker + optional year-phrase + month + "মাহ" ("যোৱা বৰ্ষৰ ডিচেম্বৰ মাহত")
        {REL_MARK}\s*(?:{UNIT}{SUFFIX}\s+)?{MONTH_NOUN}
        |
        # bare "<month> মাহত" ("জুলাই মাহত")
        {MONTH_NOUN}
        |
        # relative/approx marker + quantity + unit ("যোৱা তিনি বছৰ", "বিগত প্ৰায় ২৮০ বছৰ")
        {REL_MARK}\s*(?:{APPROX_MARK}\s+)?{QUANT}\s*{UNIT}{SUFFIX}
        |
        # relative marker + fused approx-quantity unit ("বিগত কেইমাহমানত", "যোৱা কেইদিনমানত")
        {REL_MARK}\s*{FUSED_APPROX_UNIT}{SUFFIX}
        |
        # relative marker + bare unit/weekday/event noun ("যোৱা বছৰৰ", "চলিত মাহত",
        # "যোৱা নিৰ্বাচনতো", "গতবছৰৰ" [fused, no space], "যোৱা সোমবাৰে")
        {REL_MARK}\s*(?:{UNIT}|{EVENT_NOUN}|{WEEKDAY}){SUFFIX}
        |
        # approx marker + unit, no number ("কেইবা বছৰো", "কিছুদিনৰ" [fused, no space])
        {APPROX_MARK}\s*{UNIT}{SUFFIX}
        |
        # approx/long + quantity(-range) + unit ("প্ৰায় ৩ ঘণ্টা", "দীৰ্ঘ ১০ বছৰৰ", "প্ৰায় ৩৮-৩৯ বছৰ")
        {APPROX_MARK}\s+{QUANT}(?:\s*-\s*{QUANT})?\s*{UNIT}{SUFFIX}
        |
        # bare quantity + unit, no marker ("৭ দিনৰ", "তিনিদিন", "৭৭ বছৰ", "১০৫ বছৰ")
        {QUANT}\s*{UNIT}{SUFFIX}
        |
        # bare fused approx-quantity unit ("কেইটামান" handled via APPROX_MARK+UNIT above)
        {FUSED_APPROX_UNIT}{SUFFIX}
        |
        # a duration unit with no number/marker at all ("বছৰজোৰা", "তিনিমাহজুৰি" already via QUANT,
        # but plain "মাহ"-type nouns with only a case suffix still need this catch-all).
        # NOTE: broad on purpose - trades a little over-matching risk on free-running text
        # for coverage on this closed list; tighten with a required SUFFIX if that matters.
        {UNIT}{SUFFIX}
        |
        # weekday + time-of-day, no relative marker ("বুধবাৰে দুপৰীয়া")
        {WEEKDAY}{SUFFIX}\s+{PART_OF_DAY}
        |
        # relative marker alone / with simple suffix ("আজি", "কালি", "এতিয়াও", "বৰ্তমানলৈকে")
        # - deliberately REL_MARK_BARE (excludes bare "এই"), see note above
        {REL_MARK_BARE}{SUFFIX}
        |
        # "প্ৰতি" + weekday/unit  ("প্ৰতি শনিবাৰে", "প্ৰতিদিনে", "প্ৰতিমাহে")
        প্ৰতি\s*(?:{WEEKDAY}|{UNIT})ে
    )
    """
)

# ---------------------------------------------------------------------------
# convenience: run all three and merge overlapping/adjacent spans
# ---------------------------------------------------------------------------


def extract(text: str):
    """Return a list of (start, end, matched_text, category) over `text`,
    running TIME/DATE/DURATION together and merging spans that touch or
    overlap (keeping the widest span, tagged with every category that
    contributed to it). Always normalizes `text` first."""
    text = normalize(text)
    raw = []
    for cat, pat in (("TIME", TIME), ("DATE", DATE), ("DURATION", DURATION)):
        for m in pat.finditer(text):
            if m.group():  # skip zero-length matches
                raw.append((m.start(), m.end(), cat))
    raw.sort()

    merged = []
    for start, end, cat in raw:
        if merged and start <= merged[-1][1]:  # touches/overlaps previous
            prev_start, prev_end, prev_cats = merged[-1]
            merged[-1] = (prev_start, max(prev_end, end), prev_cats | {cat})
        else:
            merged.append((start, end, {cat}))

    return [
        (start, end, text[start:end], "+".join(sorted(cats)))
        for start, end, cats in merged
    ]


if __name__ == "__main__":
    import sys

    sample = " ".join(sys.argv[1:]) or "যোৱা দেওবাৰ নিশা ৯ বাজি ৮ মিনিটত আৰু ২৫ জুলাইৰ পুৱা ১০ বজাত"
    for start, end, matched, cats in extract(sample):
        print(f"[{start:>3}:{end:<3}] {cats:<15} {matched!r}")
