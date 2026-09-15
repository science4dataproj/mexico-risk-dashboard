"""
src/reporting/domains.py

Maps each series to a business-facing "domain" and defines domain-level
metadata. This is the taxonomy used to roll up individual series into
the domain scorecard and composite fragility index (see
composite_index.py).

Design note: domains group indicators by economic function (external
stability, liquidity, etc.), NOT by data source or frequency — this is
a reporting taxonomy for stakeholders, independent of the pipeline
architecture used in src/analysis/.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class DomainInfo:
    key: str
    display_name: str
    description: str
    included_in_composite: bool
    exclusion_reason: str | None = None


DOMAIN_METADATA: dict[str, DomainInfo] = {
    "external_stability": DomainInfo(
        key="external_stability",
        display_name="Estabilidad externa",
        description="Exposición de México a choques externos: tipo de cambio y colchón de reservas.",
        included_in_composite=True,
    ),
    "liquidity": DomainInfo(
        key="liquidity",
        display_name="Liquidez",
        description="Comportamiento de los agregados monetarios (oferta de dinero).",
        included_in_composite=True,
    ),
    "rates": DomainInfo(
        key="rates",
        display_name="Tasas y política monetaria",
        description="Estabilidad del costo del dinero: CETES y tasa objetivo de Banxico.",
        included_in_composite=True,
    ),
    "real_economy": DomainInfo(
        key="real_economy",
        display_name="Economía real",
        description="Actividad económica y mercado laboral: PIB y desempleo.",
        included_in_composite=True,
    ),
    "prices": DomainInfo(
        key="prices",
        display_name="Precios",
        description="Estabilidad del nivel general de precios (INPC).",
        included_in_composite=True,
    ),
    "fiscal_solvency": DomainInfo(
        key="fiscal_solvency",
        display_name="Solvencia fiscal",
        description="Deuda pública como porcentaje del PIB.",
        included_in_composite=False,
        exclusion_reason=(
            "Annual frequency (SHCP, manual update) provides no rolling-window "
            "trend statistics (ac1_trend_tau, variance_trend_tau) — the fragility "
            "index is built exclusively from trend signals, so a domain with no "
            "trend data cannot contribute a comparable sub-score. Debt level "
            "context is still shown in the scorecard narrative, just not folded "
            "into the composite number."
        ),
    ),
}


# series_key (from config.py) -> domain key
DOMAIN_MAP: dict[str, str] = {
    "fx_rate_fix": "external_stability",
    "international_reserves": "external_stability",
    "m1": "liquidity",
    "m2": "liquidity",
    "cetes_28d": "rates",
    "target_rate": "rates",
    "quarterly_gdp": "real_economy",
    "unemployment_rate": "real_economy",
    "cpi": "prices",
    "debt_shrfsp_broad_pct_gdp": "fiscal_solvency",
}


def get_domain_for_series(series_key: str) -> str:
    """
    Returns the domain key for a given series. Raises explicitly rather
    than returning None, so a newly-added series without a domain
    mapping fails loudly instead of silently disappearing from reports.
    """
    if series_key not in DOMAIN_MAP:
        raise KeyError(
            f"Series '{series_key}' has no domain mapping in DOMAIN_MAP. "
            f"Add it to src/reporting/domains.py before it can appear in "
            f"the scorecard or composite index."
        )
    return DOMAIN_MAP[series_key]


def get_composite_domains() -> list[str]:
    """Domain keys that participate in the composite index (excludes fiscal_solvency)."""
    return [d.key for d in DOMAIN_METADATA.values() if d.included_in_composite]