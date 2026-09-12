"""
src/transform/clean.py

Unifies raw snapshots from Banxico, INEGI, and SHCP into a single tidy
("long format") panel: one row per (date, series, value). This is the
only place in the codebase that interprets each source's raw date
format — every downstream script (indices, tests, charts) should read
from data/processed/panel_long.csv and never touch data/raw directly.
"""

import json
from pathlib import Path

import pandas as pd

from src.config import (
    BANXICO_SERIES,
    INEGI_INDICATORS,
    DATA_RAW_DIR,
    DATA_PROCESSED_DIR,
)

# Reverse lookups: API ID -> our friendly key name
BANXICO_ID_TO_KEY = {v: k for k, v in BANXICO_SERIES.items()}
INEGI_ID_TO_KEY = {v: k for k, v in INEGI_INDICATORS.items()}

# Placeholder strings used by these sources to mean "no data" —
# converted to NaN, but the original string is preserved in raw_value.
MISSING_VALUE_TOKENS = {"n.d.", "n.a.", "n.s.", "-o-", "N/E", ""}


def find_latest_raw_file(source_name: str) -> Path:
    """Finds the most recently timestamped raw JSON snapshot for a source."""
    raw_dir = Path(DATA_RAW_DIR)
    matches = sorted(raw_dir.glob(f"{source_name}_*.json"))
    if not matches:
        raise FileNotFoundError(
            f"No raw snapshot found for source '{source_name}' in {raw_dir}. "
            f"Run the corresponding ingestion script first."
        )
    return matches[-1]  # timestamped filenames sort chronologically as strings


def _to_float(raw_value: str | None) -> float | None:
    """Converts a raw string value to float, treating known placeholders as NaN."""
    if raw_value is None or raw_value.strip() in MISSING_VALUE_TOKENS:
        return None
    cleaned = raw_value.replace(",", "")
    try:
        return float(cleaned)
    except ValueError:
        return None


def parse_banxico(raw: dict) -> pd.DataFrame:
    """
    Parses a Banxico SIE raw snapshot.
    Date format: DD/MM/YYYY.
    """
    rows = []
    for serie in raw["bmx"]["series"]:
        series_key = BANXICO_ID_TO_KEY.get(serie["idSerie"], serie["idSerie"])
        for obs in serie["datos"]:
            date = pd.to_datetime(obs["fecha"], format="%d/%m/%Y", errors="coerce")
            rows.append(
                {
                    "date": date,
                    "source": "banxico",
                    "series_key": series_key,
                    "raw_value": obs["dato"],
                    "value": _to_float(obs["dato"]),
                }
            )
    return pd.DataFrame(rows)


def parse_inegi(raw: dict) -> pd.DataFrame:
    """
    Parses an INEGI Indicadores raw snapshot.
    Date format depends on FREQ:
      - FREQ "8" (monthly): TIME_PERIOD is "YYYY/MM"
      - FREQ "4" (quarterly): TIME_PERIOD is "YYYY/Q" where Q is the
        QUARTER NUMBER (01-04), NOT a month. We map quarter N to the
        last month of that quarter (Q1->03, Q2->06, Q3->09, Q4->12),
        day 1, as a documented convention — this is a representative
        date for the quarter, not a literal calendar date.
    """
    rows = []
    for serie in raw["Series"]:
        series_key = INEGI_ID_TO_KEY.get(serie["INDICADOR"], serie["INDICADOR"])
        freq = serie.get("FREQ")

        for obs in serie["OBSERVATIONS"]:
            period = obs["TIME_PERIOD"]
            year_str, period_num_str = period.split("/")
            year = int(year_str)
            period_num = int(period_num_str)

            if freq == "4":  # quarterly
                month = period_num * 3
                date = pd.Timestamp(year=year, month=month, day=1)
            else:  # monthly (freq "8") — treat as default
                date = pd.Timestamp(year=year, month=period_num, day=1)

            rows.append(
                {
                    "date": date,
                    "source": "inegi",
                    "series_key": series_key,
                    "raw_value": obs["OBS_VALUE"],
                    "value": _to_float(obs["OBS_VALUE"]),
                }
            )
    return pd.DataFrame(rows)


def parse_shcp(raw: dict) -> pd.DataFrame:
    """
    Parses a parsed SHCP snapshot (already produced by src/ingestion/shcp.py).
    Annual data only — each year is represented as December 31 of that year.
    """
    rows = []
    for year_str, raw_value in raw["debt_shrfsp_broad_pct_gdp"].items():
        year = int(year_str)
        date = pd.Timestamp(year=year, month=12, day=31)
        rows.append(
            {
                "date": date,
                "source": "shcp",
                "series_key": "debt_shrfsp_broad_pct_gdp",
                "raw_value": raw_value,
                "value": _to_float(raw_value),
            }
        )
    return pd.DataFrame(rows)


def build_unified_panel() -> pd.DataFrame:
    """
    Loads the latest raw snapshot from each source, parses them into a
    common schema, and concatenates into one long-format panel.
    """
    banxico_raw = json.loads(find_latest_raw_file("banxico").read_text(encoding="utf-8"))
    inegi_raw = json.loads(find_latest_raw_file("inegi").read_text(encoding="utf-8"))
    shcp_raw = json.loads(find_latest_raw_file("shcp").read_text(encoding="utf-8"))

    panel = pd.concat(
        [
            parse_banxico(banxico_raw),
            parse_inegi(inegi_raw),
            parse_shcp(shcp_raw),
        ],
        ignore_index=True,
    )

    panel = panel.sort_values(["series_key", "date"]).reset_index(drop=True)
    return panel


def save_processed_panel(panel: pd.DataFrame) -> Path:
    """Saves the unified panel to data/processed/panel_long.csv."""
    processed_dir = Path(DATA_PROCESSED_DIR)
    processed_dir.mkdir(parents=True, exist_ok=True)

    filepath = processed_dir / "panel_long.csv"
    panel.to_csv(filepath, index=False)
    return filepath


def run() -> Path:
    panel = build_unified_panel()
    return save_processed_panel(panel)


if __name__ == "__main__":
    saved_path = run()
    print(f"Saved unified panel to {saved_path}")