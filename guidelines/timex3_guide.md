# TIMEX3 Normalized Code Reference Guide

Every extracted temporal expression returns four core attributes:
* **`type`**: Semantic category (`DATE`, `TIME`, `DURATION`, or `SET`).
* **`value`**: Standardized ISO-8601-based normalized representation.
* **`mod`**: Optional modifier indicating vagueness, boundaries, or approximations.
* **`tid`**: Unique expression identifier within the document (e.g., `t1`, `t2`).

---

## 1. Core `type` Categories

| `type` | Description | Assamese Example | Normalized `value` |
| :--- | :--- | :--- | :--- |
| **`DATE`** | Calendar date, week, month, season, year, decade, or century | কালি (Yesterday), ১৪ এপ্ৰিল (14 April) | `2026-11-12`, `XXXX-04-14` |
| **`TIME`** | Specific clock time or named part of a day | আজি ৰাতিপুৱা (This morning), সন্ধিয়া ৬ বজাত (At 6 PM) | `2026-11-13TMO`, `2026-11-13T18:00` |
| **`DURATION`** | Length or span of elapsed time | তিনি দিন (Three days), দুঘণ্টা (Two hours) | `P3D`, `PT2H` |
| **`SET`** | Recurring or periodic temporal interval | প্ৰতি সোমবাৰে (Every Monday), প্ৰতি বছৰে (Every year) | `XXXX-WXX-1`, `R/P1Y` |

---

## 2. Exhaustive `value` Format Reference

### A. Calendar Dates (`type="DATE"`)

| Pattern | Meaning | Example `value` | Example Trigger / Interpretation |
| :--- | :--- | :--- | :--- |
| `YYYY-MM-DD` | Exact calendar date | `2026-11-13` | November 13, 2026 / আজি (Today, anchored to DCT) |
| `YYYY-MM` | Specific year and month | `2026-11` | November 2026 / এই মাহত (This month) |
| `YYYY` | Specific calendar year | `2026` | The year 2026 / চলিত বৰ্ষত |
| `YYYX` | Specific decade | `199X` | The 1990s / নব্বৈৰ দশকত |
| `YYXX` | Specific century | `20XX` | The 21st century / একবিংশ শতিকা |
| `YYYY-Www` | ISO calendar week (`01`–`53`) | `2026-W46` | Week 46 of 2026 / এই সপ্তাহত (This week) |
| `YYYY-Www-D` | Day of ISO week (`1`=Mon … `7`=Sun) | `2026-W46-5` | Friday (`5`) of week 46 in 2026 |
| `YYYY-Www-WE` | Weekend of a specific ISO week | `2026-W46-WE` | Weekend of week 46 / অহা সপ্তাহৰ শেষত |
| `YYYY-SP` | Spring of a specific year | `2026-SP` | Spring 2026 / বসন্ত কাল |
| `YYYY-SU` | Summer of a specific year | `2026-SU` | Summer 2026 / গ্ৰীষ্ম কাল |
| `YYYY-FA` | Autumn / Fall of a specific year | `2026-FA` | Autumn 2026 / শৰৎ বা হেমন্ত কাল |
| `YYYY-WI` | Winter of a specific year | `2026-WI` | Winter 2026 / শীত কাল |
| `YYYY-Q1` … `Q4` | Calendar quarter (`Q1`–`Q4`) | `2026-Q3` | Third quarter of 2026 |
| `YYYY-H1` / `H2` | Half-year (`H1`=Jan–Jun, `H2`=Jul–Dec) | `2026-H1` | First half of 2026 |
| `XXXX-MM-DD` | Recurring/unanchored annual date | `XXXX-04-14` | April 14 of an unspecified year (e.g., ব'হাগ বিহু) |
| `XXXX-MM` | Unspecified year, known month | `XXXX-01` | January of an unspecified year (মাঘ মাহত) |
| `XXXX-WXX-D` | Unanchored day of the week | `XXXX-WXX-7` | Sunday (`7`) of an unspecified week (দেওবাৰে) |

---

### B. Clock Times & Parts of Day (`type="TIME"`)

*Note: `T` separates the calendar date from the time component.*

| Pattern | Meaning | Example `value` | Example Trigger / Interpretation |
| :--- | :--- | :--- | :--- |
| `YYYY-MM-DDTHH:MM` | Date + 24-hour clock time | `2026-11-13T16:24` | 4:24 PM on Nov 13, 2026 (বিয়লি ৪:২৪ বজাত) |
| `YYYY-MM-DDTHH:MM:SS` | Date + clock time with seconds | `2026-11-13T09:30:00` | 9:30:00 AM on Nov 13, 2026 |
| `YYYY-MM-DDTHH` | Date + approximate hour | `2026-11-13T14` | Around 2:00 PM on Nov 13, 2026 |
| `YYYY-MM-DDTMO` | Morning of a specific date | `2026-11-13TMO` | Morning (ৰাতিপুৱা / পুৱা) |
| `YYYY-MM-DDTAF` | Afternoon of a specific date | `2026-11-13TAF` | Afternoon (বিয়লি / আবেলি) |
| `YYYY-MM-DDTEV` | Evening of a specific date | `2026-11-13TEV` | Evening (সন্ধিয়া / গধূলি) |
| `YYYY-MM-DDTNI` | Night of a specific date | `2026-11-13TNI` | Night (ৰাতি / নিশা) |
| `YYYY-MM-DDTDT` | Daytime / working hours of a date | `2026-11-13TDT` | Daytime (দিনৰ ভাগত) |
| `YYYY-MM-DDTMI` | Midday / noon of a specific date | `2026-11-13TMI` | Noon / midday (দুপৰীয়া) |
| `XXXX-WXX-DTNI` | Unanchored day + part of day | `XXXX-WXX-5TNI` | Friday night (শুকুৰবাৰে ৰাতি) |

---

### C. Relative & Deictic Reference Tokens (`type="DATE"` or `"TIME"`)

| Token | Meaning | Example Trigger / Interpretation |
| :--- | :--- | :--- |
| `PRESENT_REF` | Unbounded present anchored to DCT | এতিয়া (Now), বৰ্তমান (Currently), সাম্প্ৰতিক সময়ত |
| `PAST_REF` | Unspecified time prior to DCT | পূৰ্বে (Previously), আগতে (Earlier), শেহতীয়াকৈ (Recently) |
| `FUTURE_REF` | Unspecified time after DCT | ভৱিষ্যতে (In the future), অচিৰেই (Soon), পাছত (Later) |

---

### D. Durations (`type="DURATION"`)

*Note: All durations start with `P` (Period). Time units (`H`, `M` for minutes, `S`) must be preceded by `T` to distinguish `M` (Months) from `TM` (Minutes).*

| Pattern | Meaning | Example `value` | Example Trigger / Interpretation |
| :--- | :--- | :--- | :--- |
| `PnY` | `n` years | `P5Y` | Five years (পাঁচ বছৰ) |
| `PnM` | `n` months | `P6M` | Six months (ছমাহ) |
| `PnW` | `n` weeks | `P2W` | Two weeks (দুসপ্তাহ) |
| `PnD` | `n` days | `P3D` | Three days (তিনি দিন) |
| `PTnH` | `n` hours | `PT4H` | Four hours (চাৰি ঘণ্টা) |
| `PTnM` | `n` minutes | `PT30M` | Thirty minutes (ত্ৰিশ মিনিট) |
| `PTnS` | `n` seconds | `PT45S` | Forty-five seconds (পঞ্চল্লিশ ছেকেণ্ড) |
| `PnYnM` / `PnDTnH` | Combined date/time duration | `P1Y6M` / `P2DT12H` | 1 year 6 months / 2 days 12 hours |
| `PXY` / `PXM` / `PXW` / `PXD` | Unspecified / vague duration | `PXD` / `PXY` | A few days (কেইবাদিনো) / Several years (কেইবাবছৰো) |
| `PTXH` / `PTXM` | Unspecified / vague short duration | `PTXH` | A few hours (কেইবাঘণ্টাও) |

---

### E. Recurring Sets (`type="SET"`)

| Pattern | Meaning | Example `value` | Example Trigger / Interpretation |
| :--- | :--- | :--- | :--- |
| `R/PnD` (`W`, `M`, `Y`) | Indefinite repetition every `n` units | `R/P1D` / `R/P1Y` | Daily (প্ৰতিদিনে) / Yearly (প্ৰতি বছৰে) |
| `Rn/PnD` | Bounded repetition (`n` times) | `R3/P1M` | Three times a month (মাহত তিনিবাৰ) |
| `XXXX-WXX-D` | Weekly recurrence on day `D` | `XXXX-WXX-1` | Every Monday (প্ৰতি সোমবাৰে) |
| `XXXX-MM-DD` | Annual recurrence on calendar date | `XXXX-01-26` | Every January 26 (প্ৰতি ২৬ জানুৱাৰীত) |
| `XXXX-WXX-DTNI` | Weekly recurrence on day + time | `XXXX-WXX-6TEV` | Every Saturday evening (প্ৰতি শনিবাৰে সন্ধিয়া) |

---

## 3. Modifier (`mod`) Reference

The `mod` attribute refines the boundary, frequency, or certainty of a `value`.

| `mod` Code | Meaning | Example Trigger | Combined Example (`value` + `mod`) |
| :--- | :--- | :--- | :--- |
| **`BEFORE`** | Strictly prior to the given point | আগতে (before) | `2026-11-13` + `BEFORE` |
| **`AFTER`** | Strictly after the given point | পাছত (after) | `2026-11-13` + `AFTER` |
| **`ON_OR_BEFORE`** | Up to and including the given point | ভিতৰত / লৈকে (by / no later than) | `2026-11-13` + `ON_OR_BEFORE` |
| **`ON_OR_AFTER`** | Starting from and including the point | পৰা (from / starting on) | `2026-11-13` + `ON_OR_AFTER` |
| **`LESS_THAN`** | Strictly shorter than a duration | কম সময়ত (less than 2 hours) | `PT2H` + `LESS_THAN` |
| **`MORE_THAN`** | Strictly longer than a duration | অধিক সময় (more than 3 days) | `P3D` + `MORE_THAN` |
| **`EQUAL_OR_LESS`** | At most the stated duration | সৰ্বাধিক (at most 1 week) | `P1W` + `EQUAL_OR_LESS` |
| **`EQUAL_OR_MORE`** | At least the stated duration | কমেও (at least 5 years) | `P5Y` + `EQUAL_OR_MORE` |
| **`START`** | Beginning phase of a period | আৰম্ভণিতে / পহিলা (early / start of) | `2026-11` + `START` (Early Nov 2026) |
| **`MID`** | Middle phase of a period | মাজভাগত (mid-month / mid-year) | `2026-11` + `MID` (Mid-Nov 2026) |
| **`END`** | Final phase of a period | শেষত / অন্তিম ভাগত (late / end of) | `2026-11` + `END` (Late Nov 2026) |
| **`APPROX`** | Approximate or estimated value | প্ৰায় (about / around / approximately) | `P10Y` + `APPROX` (Around 10 years) |