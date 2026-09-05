# -*- coding: utf-8 -*-
"""
Extract the gold TIMEX3 annotations from the annotated HTML into a CSV.

Two things the earlier version missed:

  * The document creation time is in a <DCT ...> element, not a <TIMEX3> one,
    so a pattern looking only for <TIMEX3 ...> never saw it - which is why the
    CSV had no t0 rows and nothing to resolve "আজি" or "যোৱা সোমবাৰে" against.
    Each DCT is now emitted as the first row of its document.
  * beginPoint, endPoint and freq were not among the columns, so 141
    annotations lost an attribute on the way out.

    python3 timex3_annotation_extraction.py                    # datasets/*.html
    python3 timex3_annotation_extraction.py "corpus/*.html" out.csv
"""

import csv
import re
import sys
import unicodedata
from glob import glob

# <DCT ...>...</DCT> and <TIMEX3 ...>...</TIMEX3>, self-closing forms included
TAG_RE = re.compile(
    r"<(TIMEX3|DCT)\s+([^>]*?)(?:/>|>(.*?)</\1>)", re.DOTALL | re.IGNORECASE
)
DOCUMENT_RE = re.compile(r"<document>(.*?)</document>", re.DOTALL | re.IGNORECASE)
ATTR_RE = re.compile(r"(\w+)=[\"']([^\"']*)[\"']")

FIELDNAMES = [
    "file_name", "document", "tag", "tid", "type", "value", "temporalFunction",
    "anchorTimeID", "beginPoint", "endPoint", "freq", "mod",
    "functionInDocument", "expression",
]


def extract_timex3_to_csv(file_list, output_csv_path="timex3_annotations.csv"):
    rows = []

    for file_path in file_list:
        try:
            with open(file_path, "r", encoding="utf-8") as handle:
                content = unicodedata.normalize("NFC", handle.read())
        except OSError as error:
            print(f"Error reading {file_path}: {error}")
            continue

        # documents are numbered so that each t0 stays tied to its own text
        documents = DOCUMENT_RE.findall(content) or [content]
        for number, document in enumerate(documents, start=1):
            for match in TAG_RE.finditer(document):
                tag, attr_string, text = match.groups()
                attrs = dict(ATTR_RE.findall(attr_string))
                row = {name: "" for name in FIELDNAMES}
                row.update(
                    file_name=file_path,
                    document=number,
                    tag=tag.upper(),
                    expression=(text or attrs.get("value", "")).strip(),
                    **{k: v for k, v in attrs.items() if k in FIELDNAMES},
                )
                rows.append(row)

    with open(output_csv_path, "w", encoding="utf-8-sig", newline="") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)

    tags = sum(r["tag"] == "TIMEX3" for r in rows)
    dcts = sum(r["tag"] == "DCT" for r in rows)
    print(f"Wrote {len(rows)} rows to '{output_csv_path}' "
          f"({tags} TIMEX3 tags, {dcts} document creation times).")
    return rows


if __name__ == "__main__":
    pattern = sys.argv[1] if len(sys.argv) > 1 else "datasets/*.html"
    output = sys.argv[2] if len(sys.argv) > 2 else "timex3_annotations.csv"
    extract_timex3_to_csv(sorted(glob(pattern)), output)
