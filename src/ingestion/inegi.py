"""
src/ingestion/inegi.py
Fetches raw indicator data from INEGI's Indicadores API and stores an
unmodified snapshot in data/raw. This module does NOT clean or transform
data — that responsibility belongs to src/transform/clean.py.
"""

import json
import os
from datetime import datetime, UTC
from pathlib import Path

import requests
from dotenv import load_dotenv

from src.config import INEGI_INDICATORS, INEGI_BASE_URL, DATA_RAW_DIR

load_dotenv()

INEGI_TOKEN = os.getenv("INEGI_TOKEN")

# Fixed positional path parameters required by INEGI's API (see their docs).
LANGUAGE = "es"
GEO_AREA = "00"          # 00 = national level
RECENT_ONLY = "false"    # false = full historical series; true = latest value only
SOURCE_VERSION = "BIE-BISE/2.0"


def fetch_inegi_indicators(indicator_ids: list[str]) -> dict:
    """
    Fetch one or more INEGI indicators in a single API call.

    Args:
        indicator_ids: list of INEGI indicator IDs (e.g. ["735879", "444603"])

    Returns:
        Parsed JSON response as a dict.

    Raises:
        RuntimeError: if INEGI_TOKEN is not set, or the API call fails.
    """
    if not INEGI_TOKEN:
        raise RuntimeError(
            "INEGI_TOKEN not found. Set it in your .env file "
            "(see .env.example)."
        )

    ids_param = ",".join(indicator_ids)
    # NOTE: unlike Banxico, INEGI expects the token as part of the URL path,
    # not as a query parameter. Never print or log `url` directly — it
    # contains the token in plain text.
    url = (
        f"{INEGI_BASE_URL}/{ids_param}/{LANGUAGE}/{GEO_AREA}/"
        f"{RECENT_ONLY}/{SOURCE_VERSION}/{INEGI_TOKEN}"
    )

    response = requests.get(url, params={"type": "json"}, timeout=30)
    response.raise_for_status()

    return response.json()


def save_raw_snapshot(payload: dict, source_name: str = "inegi") -> Path:
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
    """Entry point: fetch all configured INEGI indicators and save the snapshot."""
    indicator_ids = list(INEGI_INDICATORS.values())
    payload = fetch_inegi_indicators(indicator_ids)
    return save_raw_snapshot(payload)


if __name__ == "__main__":
    saved_path = run()
    print(f"Saved INEGI snapshot to {saved_path}")