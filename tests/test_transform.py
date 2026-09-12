"""
tests/test_transform.py
"""

from src.transform.clean import _to_float


def test_to_float_handles_comma_thousands_separator():
    """
    Regression test: Banxico returns large monetary figures (M1, M2,
    reserves) with comma thousands separators, e.g. "1,817,196,846.58".
    Without stripping commas, float() raises ValueError and the value
    is silently dropped as missing — this happened in practice on
    2026-09-12 and went undetected until a manual data-quality check.
    """
    assert _to_float("1,817,196,846.58") == 1817196846.58
    assert _to_float("11150071721.09") == 11150071721.09  # no commas, still works


def test_to_float_handles_missing_value_tokens():
    assert _to_float("n.d.") is None
    assert _to_float("n.a.") is None
    assert _to_float(None) is None


def test_to_float_returns_none_for_unparseable_string():
    assert _to_float("not_a_number") is None