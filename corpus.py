"""
Read the annotated Assamese TIMEX3 corpus.

Each file holds a sequence of

    <document>
      <DCT tid="t0" ... value="2026-08-20T13:40:00+05:30"
           functionInDocument="CREATION_TIME">...</DCT>
      <text> ... <TIMEX3 ...>expression</TIMEX3> ... </text>
    </document>

`load_documents` returns, for every document, the document creation time, the
plain text with the tags removed, and the gold annotations with their character
offsets into that plain text - which is what makes an end-to-end comparison
against the extractor possible.

Note the DCT sits in a <DCT> element, not a <TIMEX3> one, so a pattern that
only looks for <TIMEX3 ...> silently skips it.
"""

from __future__ import annotations

import datetime as _dt
import glob as _glob
import re
import unicodedata
from dataclasses import dataclass, field
from typing import Dict, List

DOCUMENT_RE = re.compile(r"<document>(.*?)</document>", re.DOTALL | re.IGNORECASE)
DCT_RE = re.compile(r"<DCT\s+([^>]+?)\s*/?>", re.DOTALL | re.IGNORECASE)
TEXT_RE = re.compile(r"<text>(.*?)</text>", re.DOTALL | re.IGNORECASE)
TIMEX_RE = re.compile(r"<TIMEX3\s+([^>]+?)>(.*?)</TIMEX3>", re.DOTALL | re.IGNORECASE)
ATTR_RE = re.compile(r"(\w+)=[\"']([^\"']*)[\"']")

ATTRIBUTES = (
    "tid", "type", "value", "temporalFunction", "anchorTimeID",
    "beginPoint", "endPoint", "freq", "mod", "functionInDocument",
)


def _normalize(text: str) -> str:
    return unicodedata.normalize("NFC", text)


@dataclass
class Annotation:
    """One gold <TIMEX3> element, with its span in the untagged text."""

    attrs: Dict[str, str]
    expression: str
    start: int
    end: int

    def get(self, name: str, default: str = "") -> str:
        return self.attrs.get(name, default)


@dataclass
class Document:
    file_name: str
    index: int
    dct: _dt.datetime
    text: str                                   # tags removed
    annotations: List[Annotation] = field(default_factory=list)

    @property
    def dct_date(self) -> _dt.date:
        return self.dct.date()


def _parse_dct(raw: str) -> _dt.datetime:
    """The DCT value is an ISO timestamp, e.g. 2026-08-20T13:40:00+05:30."""
    return _dt.datetime.fromisoformat(raw)


def _strip_tags(body: str) -> tuple[str, List[Annotation]]:
    """Remove the TIMEX3 tags, keeping each expression's offset in the result."""
    plain, annotations, cursor = [], [], 0
    length = 0
    for match in TIMEX_RE.finditer(body):
        before = body[cursor:match.start()]
        plain.append(before)
        length += len(before)

        expression = match.group(2)
        annotations.append(
            Annotation(
                attrs=dict(ATTR_RE.findall(match.group(1))),
                expression=expression.strip(),
                start=length + (len(expression) - len(expression.lstrip())),
                end=length + len(expression.rstrip()),
            )
        )
        plain.append(expression)
        length += len(expression)
        cursor = match.end()

    plain.append(body[cursor:])
    return "".join(plain), annotations


def load_documents(pattern: str = "datasets/*.html") -> List[Document]:
    """Every annotated document matching `pattern`, in file order."""
    documents: List[Document] = []
    for file_name in sorted(_glob.glob(pattern)):
        content = _normalize(open(file_name, encoding="utf-8").read())
        for index, body in enumerate(DOCUMENT_RE.findall(content)):
            dct_match = DCT_RE.search(body)
            text_match = TEXT_RE.search(body)
            if not (dct_match and text_match):
                continue
            attrs = dict(ATTR_RE.findall(dct_match.group(1)))
            text, annotations = _strip_tags(text_match.group(1))
            documents.append(
                Document(
                    file_name=file_name,
                    index=index,
                    dct=_parse_dct(attrs["value"]),
                    text=text,
                    annotations=annotations,
                )
            )
    return documents


if __name__ == "__main__":
    docs = load_documents()
    print(f"{len(docs)} documents, "
          f"{sum(len(d.annotations) for d in docs)} annotations")
    first = docs[0]
    print(f"\n{first.file_name} #{first.index}  DCT={first.dct.isoformat()}")
    for a in first.annotations:
        print(f"  [{a.start:>4}:{a.end:<4}] {a.get('type'):<9} "
              f"{a.get('value'):<18} {a.expression}")
