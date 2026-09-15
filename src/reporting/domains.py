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

Bilingual design (2026-09): every user-facing string is stored as a
dict keyed by language code ({"es": ..., "en": ...}), computed once at
the source, never translated downstream. This is deliberate: a single
source of truth per string, rather than two parallel files that could
drift out of sync as the project grows (see SERIES_METADATA.md,
Decisions Log #15).
"""

from dataclasses import dataclass

SUPPORTED_LANGUAGES = ("es", "en")


@dataclass(frozen=True)
class DomainInfo:
    key: str
    display_name: dict[str, str]
    description: dict[str, str]
    included_in_composite: bool
    exclusion_reason: dict[str, str] | None = None


DOMAIN_METADATA: dict[str, DomainInfo] = {
    "external_stability": DomainInfo(
        key="external_stability",
        display_name={"es": "Estabilidad externa", "en": "External stability"},
        description={
            "es": "Exposición de México a choques externos: tipo de cambio y colchón de reservas.",
            "en": "Mexico's exposure to external shocks: exchange rate and reserve buffer.",
        },
        included_in_composite=True,
    ),
    "liquidity": DomainInfo(
        key="liquidity",
        display_name={"es": "Liquidez", "en": "Liquidity"},
        description={
            "es": "Comportamiento de los agregados monetarios (oferta de dinero).",
            "en": "Behavior of monetary aggregates (money supply).",
        },
        included_in_composite=True,
    ),
    "rates": DomainInfo(
        key="rates",
        display_name={"es": "Tasas y política monetaria", "en": "Rates & monetary policy"},
        description={
            "es": "Estabilidad del costo del dinero: CETES y tasa objetivo de Banxico.",
            "en": "Stability of the cost of money: CETES and Banxico's target rate.",
        },
        included_in_composite=True,
    ),
    "real_economy": DomainInfo(
        key="real_economy",
        display_name={"es": "Economía real", "en": "Real economy"},
        description={
            "es": "Actividad económica y mercado laboral: PIB y desempleo.",
            "en": "Economic activity and labor market: GDP and unemployment.",
        },
        included_in_composite=True,
    ),
    "prices": DomainInfo(
        key="prices",
        display_name={"es": "Precios", "en": "Prices"},
        description={
            "es": "Estabilidad del nivel general de precios (INPC).",
            "en": "Stability of the general price level (CPI).",
        },
        included_in_composite=True,
    ),
    "fiscal_solvency": DomainInfo(
        key="fiscal_solvency",
        display_name={"es": "Solvencia fiscal", "en": "Fiscal solvency"},
        description={
            "es": "Deuda pública como porcentaje del PIB.",
            "en": "Public debt as a percentage of GDP.",
        },
        included_in_composite=False,
        exclusion_reason={
            "es": (
                "Frecuencia anual (SHCP, actualización manual) no genera estadísticas "
                "de tendencia rodante — el índice de fragilidad se construye "
                "exclusivamente con señales de tendencia."
            ),
            "en": (
                "Annual frequency (SHCP, manual update) provides no rolling-window "
                "trend statistics — the fragility index is built exclusively from "
                "trend signals."
            ),
        },
    ),
}


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
    if series_key not in DOMAIN_MAP:
        raise KeyError(
            f"Series '{series_key}' has no domain mapping in DOMAIN_MAP. "
            f"Add it to src/reporting/domains.py before it can appear in "
            f"the scorecard or composite index."
        )
    return DOMAIN_MAP[series_key]


def get_composite_domains() -> list[str]:
    return [d.key for d in DOMAIN_METADATA.values() if d.included_in_composite]


def get_display_name(domain_key: str, lang: str = "es") -> str:
    """
    Returns the domain's display name in the requested language.
    Raises explicitly on an unsupported language code, rather than
    silently falling back to Spanish — a missing translation should be
    caught immediately, not discovered later on the live page.
    """
    if lang not in SUPPORTED_LANGUAGES:
        raise ValueError(f"Unsupported language '{lang}'. Supported: {SUPPORTED_LANGUAGES}")
    return DOMAIN_METADATA[domain_key].display_name[lang]