"""
tests/test_stakeholder_text.py
"""

import pytest

from src.reporting.stakeholder_text import (
    STAKEHOLDER_EXPLANATIONS,
    get_stakeholder_explanation,
)
from src.reporting.domains import get_composite_domains

STATUS_IDS = ("stable", "monitor", "fragile")
LANGS = ("es", "en")


def test_every_composite_domain_has_all_status_and_language_combinations():
    """Guards against adding a new domain to the composite index without
    also writing its stakeholder explanations — a missing combination
    would only surface as a live KeyError on the dashboard otherwise."""
    for domain_key in get_composite_domains():
        assert domain_key in STAKEHOLDER_EXPLANATIONS, f"{domain_key} has no stakeholder text at all"
        for status_id in STATUS_IDS:
            for lang in LANGS:
                assert lang in STAKEHOLDER_EXPLANATIONS[domain_key].get(status_id, {}), (
                    f"{domain_key}/{status_id}/{lang} is missing"
                )


def test_get_stakeholder_explanation_returns_text():
    text = get_stakeholder_explanation("liquidity", "fragile", "es")
    assert isinstance(text, str) and len(text) > 20


def test_get_stakeholder_explanation_raises_on_unknown_combination():
    with pytest.raises(KeyError):
        get_stakeholder_explanation("liquidity", "not_a_real_status", "es")