# -*- coding: utf-8 -*-
"""
Score the pipeline against the annotated corpus.

Two evaluations, because they answer different questions:

  attributes  - given the gold spans, are the TIMEX3 attributes right?
                (the normalizer on its own)
  end-to-end  - run the extractor over the raw text, then normalize, and
                compare both the spans found and their attributes
                (the number that matters in practice)

    python3 evaluate_timex3.py            # summary
    python3 evaluate_timex3.py -v         # + every attribute mismatch
    python3 evaluate_timex3.py --spans    # + every span mismatch
"""

from __future__ import annotations

import datetime as dt
import re
import sys
from collections import Counter

from corpus import load_documents
from timex3_normalizer import CONTEXT_WINDOW, annotate_document, to_timex3

FULL_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")
FIELDS = ("type", "value", "mod", "temporalFunction",
          "anchorTimeID", "beginPoint", "endPoint", "freq")


def gold_fields(annotation) -> dict:
    return {name: annotation.get(name) for name in FIELDS}


def predicted_fields(tx) -> dict:
    row = tx.as_row()
    return {name: row[name] for name in FIELDS}


def evaluate_attributes(documents, verbose=False) -> Counter:
    """Gold spans in, attributes out."""
    counts, mismatches = Counter(), Counter()

    for doc in documents:
        focus = doc.dct_date
        for annotation in doc.annotations:
            after = doc.text[annotation.end:annotation.end + CONTEXT_WINDOW]
            tx = to_timex3(annotation.expression, dct=doc.dct_date,
                           focus=focus, context_after=after)
            gold, pred = gold_fields(annotation), predicted_fields(tx)

            counts["total"] += 1
            for name in FIELDS:
                counts[name] += gold[name] == pred[name]
            if gold == pred:
                counts["exact"] += 1
            else:
                wrong = tuple(n for n in FIELDS if gold[n] != pred[n])
                mismatches[(annotation.expression, wrong,
                            tuple(gold[n] for n in wrong),
                            tuple(pred[n] for n in wrong))] += 1

            # move the narrative date along, preferring the gold answer so one
            # bad row cannot cascade into the next
            if annotation.get("type") == "DATE" and FULL_DATE.fullmatch(gold["value"]):
                focus = dt.date.fromisoformat(gold["value"])
            elif tx.anchor_date is not None:
                focus = tx.anchor_date

    total = counts["total"]
    print(f"ATTRIBUTES (scored on gold spans): {total} annotations")
    for name in FIELDS:
        print(f"  {name:<17} {counts[name]:>4}/{total} {counts[name] / total:7.1%}")
    print(f"  {'all attributes':<17} {counts['exact']:>4}/{total} "
          f"{counts['exact'] / total:7.1%}")

    if verbose and mismatches:
        print("\n  mismatches:")
        for (expr, fields, gold, pred), n in mismatches.most_common():
            print(f"   x{n:<3} {expr:<38} {','.join(fields):<20} "
                  f"gold={'/'.join(gold) or '-':<13} pred={'/'.join(pred) or '-'}")
    return counts


def evaluate_end_to_end(documents, show_spans=False) -> Counter:
    """Raw text in, annotations out: extraction and normalization together."""
    counts, span_errors = Counter(), Counter()

    for doc in documents:
        gold = {(a.start, a.end): a for a in doc.annotations}
        pred = {(t.start, t.end): t
                for t in annotate_document(doc.text, doc.dct_date)}

        counts["gold"] += len(gold)
        counts["pred"] += len(pred)
        for span in set(gold) & set(pred):
            counts["span_hits"] += 1
            if gold_fields(gold[span]) == predicted_fields(pred[span]):
                counts["full_hits"] += 1
        for span in set(gold) - set(pred):
            span_errors[("missed", gold[span].expression)] += 1
        for span in set(pred) - set(gold):
            span_errors[("spurious", pred[span].expression)] += 1

    def prf(hits):
        precision = hits / counts["pred"]
        recall = hits / counts["gold"]
        f1 = 2 * precision * recall / (precision + recall) if hits else 0.0
        return precision, recall, f1

    print(f"\nEND-TO-END (raw text in): "
          f"{counts['gold']} gold spans, {counts['pred']} predicted")
    print("  exact span            P {:6.1%}  R {:6.1%}  F1 {:6.1%}".format(*prf(counts["span_hits"])))
    print("  span + all attributes P {:6.1%}  R {:6.1%}  F1 {:6.1%}".format(*prf(counts["full_hits"])))

    if show_spans and span_errors:
        print("\n  span errors:")
        for (kind, expr), n in span_errors.most_common(50):
            print(f"   x{n:<3} {kind:<9} {expr}")
    return counts


def main():
    pattern = "datasets/*.html"
    for arg in sys.argv[1:]:
        if not arg.startswith("-"):
            pattern = arg
    documents = load_documents(pattern)
    print(f"{len(documents)} documents\n")
    evaluate_attributes(documents, verbose="-v" in sys.argv)
    evaluate_end_to_end(documents, show_spans="--spans" in sys.argv)


if __name__ == "__main__":
    main()
