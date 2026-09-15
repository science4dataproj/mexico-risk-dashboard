"""
src/reporting/run_reporting.py
"""

import json
from datetime import datetime, UTC
from pathlib import Path

import pandas as pd

from src.config import DATA_PROCESSED_DIR
from src.reporting.composite_index import compute_composite_index
from src.reporting.narrative import generate_domain_narrative_bilingual, generate_composite_technical_summary
from src.reporting.stakeholder_text import get_stakeholder_explanation, get_composite_stakeholder_explanation

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
        narrative = generate_domain_narrative_bilingual(results_df, domain_score.domain_key)
        stakeholder = {
            lang: get_stakeholder_explanation(domain_score.domain_key, domain_score.label.status_id, lang)
            for lang in ("es", "en")
        }
        domains_output.append({
            "domain_key": domain_score.domain_key,
            "display_name": domain_score.display_name,
            "score": domain_score.score,
            "label": {"status_id": domain_score.label.status_id, **domain_score.label.text},
            "n_signals_active": domain_score.n_signals_active,
            "n_signals_possible": domain_score.n_signals_possible,
            "narrative": narrative,
            "narrative_stakeholder": stakeholder,
        })

    composite_narrative = generate_composite_technical_summary(composite.domain_scores, composite.composite_score)
    composite_stakeholder = {
        lang: get_composite_stakeholder_explanation(composite.composite_label.status_id, lang)
        for lang in ("es", "en")
    }

    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "composite_score": composite.composite_score,
        "composite_label": {"status_id": composite.composite_label.status_id, **composite.composite_label.text},
        "composite_narrative": composite_narrative,
        "composite_narrative_stakeholder": composite_stakeholder,
        "domains": domains_output,
    }


def save_scorecard(scorecard: dict) -> Path:
    Path(DATA_PROCESSED_DIR).mkdir(parents=True, exist_ok=True)
    with open(SCORECARD_PATH, "w", encoding="utf-8") as f:
        json.dump(scorecard, f, ensure_ascii=False, indent=2)
    return SCORECARD_PATH


def run() -> Path:
    return save_scorecard(build_scorecard())


if __name__ == "__main__":
    path = run()
    print(f"Saved risk scorecard to {path}\n")
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    print(f"Composite: {data['composite_score']} — {data['composite_label']['status_id']}")
    print(f"  Técnico: {data['composite_narrative']['es']}")
    print(f"  General: {data['composite_narrative_stakeholder']['es']}\n")
    for d in data["domains"]:
        print(f"[{d['label']['status_id']}] {d['display_name']['es']} (score: {d['score']})")
        print(f"  Técnico: {d['narrative']['es']}")
        print(f"  General: {d['narrative_stakeholder']['es']}\n")