import csv
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# ================= CONFIGURATION =================
INPUT_CSV = "link-to-copyrighted-documents.csv"         # Must contain 'doc_id' and 'link'
DATASET_XML = "datasets/documents_15_TIMEX3.html"     # Single file containing <document> tags
ARTICLES_DIR = "full_articles/"          # Directory of full texts named {doc_id}.txt
OUTPUT_CSV = "reproducible_dataset.csv"
# =================================================


def find_span_in_article(full_text: str, snippet: str) -> Optional[Tuple[int, int]]:
    """
    Finds the (start, end) character offsets of `snippet` inside `full_text`.
    Falls back to whitespace-insensitive regex matching if exact match fails.
    """
    # 1. Exact match
    idx = full_text.find(snippet)
    if idx != -1:
        return idx, idx + len(snippet)

    # 2. Strip outer whitespace and retry
    stripped = snippet.strip()
    idx = full_text.find(stripped)
    if idx != -1:
        return idx, idx + len(stripped)

    # 3. Whitespace-normalized regex match (handles \n vs space differences)
    tokens = stripped.split()
    if not tokens:
        return None
    pattern = r"\s+".join(re.escape(t) for t in tokens)
    match = re.search(pattern, full_text)
    if match:
        return match.start(), match.end()

    return None


def parse_document_element(doc_elem: ET.Element) -> Tuple[str, str, List[Tuple[str, str]]]:
    """
    Extracts DCT from <DCT value="..."> and clean text + relative TIMEX3 spans from <text>.
    Adjusts TIMEX3 offsets when leading whitespace inside <text> is stripped.
    """
    # 1. Extract Document Creation Time directly from <DCT value="...">
    dct = ""
    dct_elem = doc_elem.find("DCT")
    if dct_elem is not None:
        dct = dct_elem.attrib.get("value", "").strip()
        if not dct:
            dct = (dct_elem.text or "").strip()

    # 2. Extract text and TIMEX3 spans from <text> (or fallback to doc_elem)
    text_container = doc_elem.find("text")
    if text_container is None:
        text_container = doc_elem

    clean_parts: List[str] = []
    current_offset = 0
    raw_timex_records: List[Tuple[int, int, str]] = []  # (start, end, norm_val)

    def append_text(text: Optional[str]):
        nonlocal current_offset
        if text:
            clean_parts.append(text)
            current_offset += len(text)

    def walk(node: ET.Element):
        nonlocal current_offset
        if node.tag == "DCT":
            return

        if node.tag == "TIMEX3":
            expr_text = "".join(node.itertext())
            start = current_offset
            append_text(expr_text)
            end = current_offset

            norm_val = node.attrib.get("value", "")
            raw_timex_records.append((start, end, norm_val))
        else:
            append_text(node.text)
            for child in node:
                walk(child)

        if node is not text_container:
            append_text(node.tail)

    walk(text_container)
    raw_snippet = "".join(clean_parts)

    # 3. Strip outer newlines/spaces around <text> content and shift TIMEX3 spans accordingly
    leading_ws_len = len(raw_snippet) - len(raw_snippet.lstrip())
    clean_snippet = raw_snippet.strip()

    timex_records: List[Tuple[str, str]] = []
    for start, end, norm_val in raw_timex_records:
        adj_start = start - leading_ws_len
        adj_end = end - leading_ws_len
        timex_records.append((f"{adj_start}:{adj_end}", norm_val))

    return clean_snippet, dct, timex_records


def load_dataset(xml_path: str) -> Dict[str, dict]:
    """
    Parses the single file containing sequential <document> blocks.
    Assigns doc_id = "1", "2", ... based on document order.
    """
    raw_xml = Path(xml_path).read_text(encoding="utf-8")

    # Escape any bare '&' not already part of an XML entity so ET.fromstring won't fail
    raw_xml = re.sub(r"&(?!(?:amp|lt|gt|quot|apos|#\d+|#x[0-9a-fA-F]+);)", "&amp;", raw_xml)

    if not raw_xml.lstrip().startswith("<root"):
        raw_xml = f"<root>\n{raw_xml}\n</root>"

    root = ET.fromstring(raw_xml)
    dataset = {}

    for idx, doc in enumerate(root.findall(".//document"), start=1):
        doc_id = str(idx)
        snippet, dct, timex_records = parse_document_element(doc)
        dataset[doc_id] = {
            "snippet": snippet,
            "dct": dct,
            "timex": timex_records,
        }

    return dataset


def main():
    dataset = load_dataset(DATASET_XML)
    articles_path = Path(ARTICLES_DIR)

    rows_data = []
    max_timex_count = 0

    with open(INPUT_CSV, mode="r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            doc_id = row["doc_id"].strip()
            link = row["link"].strip()

            if doc_id not in dataset:
                print(f"[WARNING] doc_id '{doc_id}' not found in {DATASET_XML}. Skipping.")
                continue

            article_file = articles_path / f"{doc_id}.txt"
            if not article_file.exists():
                print(f"[WARNING] Full article file missing: {article_file}. Skipping.")
                continue

            full_text = article_file.read_text(encoding="utf-8")
            entry = dataset[doc_id]

            span = find_span_in_article(full_text, entry["snippet"])
            if span is None:
                print(f"[ERROR] Could not align dataset snippet in {article_file}.")
                doc_char_span = "NOT_FOUND"
            else:
                doc_char_span = f"{span[0]}:{span[1]}"

            timex_list = entry["timex"]
            max_timex_count = max(max_timex_count, len(timex_list))

            rows_data.append({
                "doc_id": doc_id,
                "link": link,
                "doc_char_span": doc_char_span,
                "dct": entry["dct"],
                "timex": timex_list,
            })

    # Construct dynamic headers: expression_1..N followed by timex_1..N
    expr_headers = [f"expression_{i}" for i in range(1, max_timex_count + 1)]
    timex_headers = [f"timex_{i}" for i in range(1, max_timex_count + 1)]
    fieldnames = ["doc_id", "link", "doc_char_span", "dct"] + expr_headers + timex_headers

    with open(OUTPUT_CSV, mode="w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for item in rows_data:
            out_row = {
                "doc_id": item["doc_id"],
                "link": item["link"],
                "doc_char_span": item["doc_char_span"],
                "dct": item["dct"],
            }
            for idx, (expr_span, norm_val) in enumerate(item["timex"], start=1):
                out_row[f"expression_{idx}"] = expr_span
                out_row[f"timex_{idx}"] = norm_val

            writer.writerow(out_row)

    print(f"Done! Wrote {len(rows_data)} rows to {OUTPUT_CSV} (max expressions: {max_timex_count}).")


if __name__ == "__main__":
    main()