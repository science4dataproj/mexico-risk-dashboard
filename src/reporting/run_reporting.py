"""
src/reporting/run_reporting.py

Orchestrates the reporting layer: reads data/processed/analysis_results.csv,
computes the composite fragility index and domain scorecard, attaches
narrative text to each domain, and saves the combined result to
data/processed/risk_scorecard.json.
"""

import json
from datetime import datetime, UTC
from pathlib import Path

import pandas as pd

from src.config import DATA_PROCESSED_DIR
from src.reporting.composite_index import compute_composite_index
from src.reporting.narrative import generate_domain_narrative

RESULTS_PATH = Path(DATA_PROCESSED_DIR) / "analysis_results.csv"
SCORECARD_PATH = Path(DATA_PROCESSED_DIR) / "risk_scorecard.json"


def build_scorecard() -> dict:
    if not RESULTS_PATH.exists():
        raise FileNotFoundError(
            f"{RESULTS_PATH} not found. Run `python -m src.analysis.run_analysis` first."
        )
    results_df = pd.read_csv(RESULTS_PATH)

    composite = compute_composite_index(results_df)

    domains_output = []
    for domain_score in composite.domain_scores:
        narrative = generate_domain_narrative(results_df, domain_score.domain_key)
        domains_output.append({
            "domain_key": domain_score.domain_key,
            "display_name": domain_score.display_name,
            "score": domain_score.score,
            "label": domain_score.label,
            "n_signals_active": domain_score.n_signals_active,
            "n_signals_possible": domain_score.n_signals_possible,
            "narrative": narrative,
        })

    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "composite_score": composite.composite_score,
        "composite_label": composite.composite_label,
        "domains": domains_output,
    }


def save_scorecard(scorecard: dict) -> Path:
    Path(DATA_PROCESSED_DIR).mkdir(parents=True, exist_ok=True)
    with open(SCORECARD_PATH, "w", encoding="utf-8") as f:
        json.dump(scorecard, f, ensure_ascii=False, indent=2)
    return SCORECARD_PATH


def run() -> Path:
    scorecard = build_scorecard()
    return save_scorecard(scorecard)


if __name__ == "__main__":
    path = run()
    print(f"Saved risk scorecard to {path}\n")

    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    print(f"Índice compuesto: {data['composite_score']} — {data['composite_label']}\n")
    for d in data["domains"]:
        print(f"[{d['label']}] {d['display_name']} (score: {d['score']})")
        print(f"  {d['narrative']}\n")