import csv
import glob
import re

# List of your annotated file paths
ALL_ANNOTATIONS = glob.glob("datasets/*.html")  # Replace or assign your file list here


def extract_timex3_to_csv(file_list, output_csv_path="resources/timex3_annotations.csv"):
    # Regex to capture all attributes inside TIMEX3 tag and the inner text
    # Group 1: Attributes string, Group 2: Temporal expression text
    timex_pattern = re.compile(
        r"<TIMEX3\s+([^>]+)>(.*?)</TIMEX3>", re.DOTALL | re.IGNORECASE
    )

    # Regex to parse individual key="value" pairs inside the attributes string
    attr_pattern = re.compile(r'(\w+)=["\']([^"\']*)["\']')

    rows = []

    for file_path in file_list:
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()

            # Find all <TIMEX3 ...>text</TIMEX3> matches
            matches = timex_pattern.finditer(content)

            for match in matches:
                attr_str = match.group(1)
                expression_text = match.group(2).strip()

                # Parse attributes into a dictionary
                attrs = dict(attr_pattern.findall(attr_str))

                # Build row structure
                row = {
                    "file_name": file_path,
                    "tid": attrs.get("tid", ""),
                    "type": attrs.get("type", ""),
                    "value": attrs.get("value", ""),
                    "temporalFunction": attrs.get("temporalFunction", ""),
                    "anchorTimeID": attrs.get("anchorTimeID", ""),
                    "mod": attrs.get("mod", ""),
                    "functionInDocument": attrs.get("functionInDocument", ""),
                    "expression": expression_text,
                }
                rows.append(row)

        except Exception as e:
            print(f"Error processing file {file_path}: {e}")

    # Write extracted data to CSV
    fieldnames = [
        "file_name",
        "tid",
        "type",
        "value",
        "temporalFunction",
        "anchorTimeID",
        "mod",
        "functionInDocument",
        "expression",
    ]

    with open(output_csv_path, "w", encoding="utf-8-sig", newline="") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(
        f"Successfully extracted {len(rows)} TIMEX3 tags to '{output_csv_path}'."
    )


# Execute the extraction
extract_timex3_to_csv(ALL_ANNOTATIONS)