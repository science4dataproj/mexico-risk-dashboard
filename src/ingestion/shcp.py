"""
src/ingestion/shcp.py

Parses the manually-downloaded SHCP SHRFSP debt file. This is NOT part
of the automated cron pipeline — SHCP's dashboard (presto.hacienda.gob.mx)
has no export button or API, so the file must be downloaded by hand
(see SERIES_METADATA.md for the click-by-click procedure). This script
automates only the parsing step, not the retrieval step.

IMPORTANT: despite the .xls extension, the file SHCP exports is actually
SpreadsheetML (Excel 2003 XML format), not a real binary/OOXML workbook.
Standard libraries (pandas.read_excel, openpyxl, xlrd) cannot read it
directly — it must be parsed as XML.
"""

import json
import re
from datetime import datetime, UTC
from pathlib import Path

import xml.etree.ElementTree as ET

from src.config import DATA_RAW_DIR

NS = {"ss": "urn:schemas-microsoft-com:office:spreadsheet"}

# The row we want is the unqualified aggregate total. Sub-rows like
# "Interno", "Externos", "Gobierno Federal" etc. are deliberately
# excluded (see SERIES_METADATA.md, section 3).
TARGET_ROW_LABEL = "Saldo histórico de los RFSP"


def _repair_mojibake(raw_bytes: bytes) -> bytes:
    """
    Fixes a recurring SHCP export glitch: a stray 0xC3 byte gets
    prepended to an otherwise-Latin-1-encoded accented character,
    producing invalid UTF-8 that breaks XML parsing.

    Rather than hardcoding the specific characters seen once, this
    finds any 0xC3 byte NOT followed by a valid UTF-8 continuation
    byte (0x80-0xBF), and re-encodes the following byte as if it were
    meant to stand alone (interpreted as Latin-1), which is the
    pattern observed in practice.
    """
    def fix(match: re.Match) -> bytes:
        bad_byte = match.group(1)
        char = bad_byte.decode("latin-1")
        return char.encode("utf-8")

    return re.sub(rb"\xc3([^\x80-\xbf])", fix, raw_bytes)


def _cell_text(cell: ET.Element) -> str | None:
    """Extracts text from a cell, handling both plain and <label>-wrapped data."""
    data = cell.find("ss:Data", NS)
    if data is None:
        return None
    text = "".join(data.itertext()).strip()
    return text or None


def parse_shcp_file(filepath: str | Path) -> dict:
    """
    Parses a manually-downloaded SHCP SHRFSP SpreadsheetML file.

    Returns:
        dict with keys:
            - "debt_shrfsp_broad_pct_gdp": {year: value_or_None}
            - "footnotes": list of footnote strings, preserved verbatim
            - "source_query_date": the "Consulta Actual" date embedded
              in the file, if found

    Raises:
        ValueError: if the expected total row is not found.
    """
    with open(filepath, "rb") as f:
        raw = f.read()

    raw = _repair_mojibake(raw)
    root = ET.fromstring(raw)

    worksheet = root.find("ss:Worksheet", NS)
    table = worksheet.find("ss:Table", NS)
    rows = table.findall("ss:Row", NS)

    row_texts = [
        [_cell_text(c) for c in r.findall("ss:Cell", NS)] for r in rows
    ]

    # Row 0 contains the title, including "Consulta Actual: DD/M/YYYY"
    title_text = row_texts[0][0] or ""
    query_date_match = re.search(r"Consulta Actual:\s*([\d/]+)", title_text)
    source_query_date = query_date_match.group(1) if query_date_match else None

    # Year headers are the row whose first cell is a 4-digit year
    year_row = next(
        (r for r in row_texts if r and r[0] and re.fullmatch(r"\d{4}", r[0])),
        None,
    )
    if year_row is None:
        raise ValueError("Could not locate the year header row in the SHCP file.")
    years = year_row

    # Total row: match the label exactly, not "Interno"/"Externos"/etc.
    total_row = next(
        (r for r in row_texts if r and r[0] == TARGET_ROW_LABEL),
        None,
    )
    if total_row is None:
        raise ValueError(
            f"Could not find the row labeled '{TARGET_ROW_LABEL}'. "
            "The file structure may have changed — inspect manually."
        )
    values = total_row[1:]

    debt_by_year = dict(zip(years, values))

    # Footnote rows: short strings following the data block, no leading digit
    footnotes = [
        r[0] for r in row_texts
        if r and r[0] and not re.match(r"^\d", r[0])
        and r[0] not in (TARGET_ROW_LABEL, "Concepto", "Porcentajes del PIB")
        and len(r) == 1
    ]

    return {
        "debt_shrfsp_broad_pct_gdp": debt_by_year,
        "footnotes": footnotes,
        "source_query_date": source_query_date,
    }


def save_raw_snapshot(payload: dict, source_name: str = "shcp") -> Path:
    """Saves the parsed result to data/raw with a timestamped filename."""
    raw_dir = Path(DATA_RAW_DIR)
    raw_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    filepath = raw_dir / f"{source_name}_{timestamp}.json"

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    return filepath


def run(source_filepath: str | Path) -> Path:
    """
    Entry point. Unlike banxico.run()/inegi.run(), this takes a filepath
    argument — it processes whatever file you most recently downloaded
    by hand, it does not fetch anything itself.
    """
    payload = parse_shcp_file(source_filepath)
    return save_raw_snapshot(payload)


if __name__ == "__main__":
    import sys

    if len(sys.argv) != 2:
        print("Usage: python -m src.ingestion.shcp <path_to_downloaded_file.xls>")
        sys.exit(1)

    saved_path = run(sys.argv[1])
    print(f"Saved SHCP snapshot to {saved_path}")