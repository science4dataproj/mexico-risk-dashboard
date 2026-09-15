"""
tests/test_domains.py
"""

import pytest

from src.reporting.domains import (
    DOMAIN_MAP,
    DOMAIN_METADATA,
    get_domain_for_series,
    get_composite_domains,
)
from src.config import BANXICO_SERIES, INEGI_INDICATORS


def test_every_pipeline_series_has_a_domain():
    """
    Every series actually produced by the pipeline (Banxico + INEGI
    keys from config.py, plus the SHCP debt series) must have a domain
    mapping — catches the case where a new series gets added to
    ingestion but someone forgets to map it here.
    """
    all_series_keys = (
        list(BANXICO_SERIES.keys())
        + list(INEGI_INDICATORS.keys())
        + ["debt_shrfsp_broad_pct_gdp"]
    )
    for key in all_series_keys:
        assert key in DOMAIN_MAP, f"'{key}' is missing from DOMAIN_MAP"


def test_get_domain_for_series_raises_on_unknown_series():
    with pytest.raises(KeyError):
        get_domain_for_series("not_a_real_series")


def test_get_domain_for_series_returns_correct_domain():
    assert get_domain_for_series("m2") == "liquidity"
    assert get_domain_for_series("fx_rate_fix") == "external_stability"


def test_fiscal_solvency_excluded_from_composite():
    composite_domains = get_composite_domains()
    assert "fiscal_solvency" not in composite_domains
    assert len(composite_domains) == 5


def test_every_domain_metadata_key_matches_its_dict_key():
    """Guards against a copy-paste error where the DomainInfo.key
    doesn't match the dictionary key it's stored under."""
    for dict_key, info in DOMAIN_METADATA.items():
        assert dict_key == info.key


from src.reporting.domains import get_display_name, SUPPORTED_LANGUAGES


def test_every_domain_has_both_languages():
    """
    Guards against adding a new domain with only one language filled
    in — every display_name, description, and (if present)
    exclusion_reason dict must have both 'es' and 'en' keys.
    """
    for domain_key, info in DOMAIN_METADATA.items():
        for lang in SUPPORTED_LANGUAGES:
            assert lang in info.display_name, f"{domain_key} missing '{lang}' display_name"
            assert lang in info.description, f"{domain_key} missing '{lang}' description"
            if info.exclusion_reason is not None:
                assert lang in info.exclusion_reason, f"{domain_key} missing '{lang}' exclusion_reason"


def test_get_display_name_returns_correct_language():
    assert get_display_name("liquidity", "es") == "Liquidez"
    assert get_display_name("liquidity", "en") == "Liquidity"


def test_get_display_name_rejects_unsupported_language():
    import pytest
    with pytest.raises(ValueError):
        get_display_name("liquidity", "fr")