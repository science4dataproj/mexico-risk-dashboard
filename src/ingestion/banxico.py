"""
src/ingestion/banxico.py
Fetches raw time series data from Banxico's SIE API and stores an
unmodified snapshot in data/raw. This module does NOT clean or transform
data — that responsibility belongs to src/transform/clean.py.
"""

import json
import os
from datetime import datetime, date, UTC
from pathlib import Path

import requests
from dotenv import load_dotenv

from src.config import BANXICO_SERIES, BANXICO_BASE_URL, DATA_RAW_DIR, HIST_START_DATE

load_dotenv()

BANXICO_TOKEN = os.getenv("BANXICO_TOKEN")


def fetch_banxico_series(
    series_ids: list[str],
    start_date: str = HIST_START_DATE,
    end_date: str | None = None,
) -> dict:
    """
    Fetch one or more Banxico SIE series in a single API call.

    Args:
        series_ids: list of Banxico series IDs (e.g. ["SF43718", "SF311418"])
        start_date: ISO date string (YYYY-MM-DD)
        end_date: ISO date string; defaults to today if not provided

    Returns:
        Parsed JSON response as a dict.

    Raises:
        RuntimeError: if BANXICO_TOKEN is not set, or the API call fails.
    """
    if not BANXICO_TOKEN:
        raise RuntimeError(
            "BANXICO_TOKEN not found. Set it in your .env file "
            "(see .env.example)."
        )

    if end_date is None:
        end_date = date.today().isoformat()

    ids_param = ",".join(series_ids)
    url = f"{BANXICO_BASE_URL}/{ids_param}/datos/{start_date}/{end_date}"

    response = requests.get(
        url,
        params={"token": BANXICO_TOKEN},
        timeout=30,
    )
    response.raise_for_status()

    return response.json()


def save_raw_snapshot(payload: dict, source_name: str = "banxico") -> Path:
    """
    Saves a raw API response to data/raw with a timestamped filename,
    so every historical pull is preserved and auditable via git history.
    """
    raw_dir = Path(DATA_RAW_DIR)
    raw_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    filepath = raw_dir / f"{source_name}_{timestamp}.json"

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    return filepath


def run() -> Path:
    """Entry point: fetch all configured Banxico series and save the snapshot."""
    series_ids = list(BANXICO_SERIES.values())
    payload = fetch_banxico_series(series_ids)
    return save_raw_snapshot(payload)


if __name__ == "__main__":
    saved_path = run()
    print(f"Saved Banxico snapshot to {saved_path}")