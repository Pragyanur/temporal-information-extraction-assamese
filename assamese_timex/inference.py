import datetime as _dt
import re
from assamese_timex.normalizer import annotate_document, to_timex3, tag_document

ISO_DATE_PREFIX = re.compile(r"^(\d{4}-\d{2}-\d{2})")


def resolve_dct(text: str, dct: _dt.date | None = None) -> _dt.date:
    """
    Returns the provided `dct`. If `dct` is None, extracts temporal expressions
    anchored to today's date and selects the most recent date in the document
    (not in the future relative to today). Falls back to today's date.
    """
    if dct is not None:
        return dct

    today = _dt.date.today()
    candidate_dates: list[_dt.date] = []

    # First pass: anchor to today to resolve any relative expressions
    for expr in annotate_document(text, today):
        if expr.type in {"DATE", "TIME"} and expr.value:
            match = ISO_DATE_PREFIX.match(expr.value)
            if match:
                try:
                    parsed_date = _dt.date.fromisoformat(match.group(1))
                    if parsed_date <= today:
                        candidate_dates.append(parsed_date)
                except ValueError:
                    continue

    return max(candidate_dates) if candidate_dates else today


def infer(text: str, dct: _dt.date | None = None):
    resolved_dct = resolve_dct(text, dct)
    for temporal_expression in annotate_document(text, resolved_dct):
        print(
            f"{temporal_expression.expression} "
            f"{temporal_expression.tid:<4} "
            f"{temporal_expression.type:<9} "
            f"{temporal_expression.value:<20} "
            f"{temporal_expression.mod:<13}"
        )


def write_on_document(text: str, dct: _dt.date | None = None) -> str:
    resolved_dct = resolve_dct(text, dct)
    return tag_document(text, resolved_dct)