"""
config.py
Centralizes series IDs, paths, and constants for the project.
"""

# --- Banxico SIE (Sistema de Información Económica) ---
# IDs verified against: https://www.banxico.org.mx/SieAPIRest/service/v1/doc/catalogoSeries
BANXICO_SERIES = {
    "fx_rate_fix": "SF43718",           # MXN per USD, FIX rate
    "cetes_28d": "SF60633",             # 28-day CETES rate
    "target_rate": "SF61745",           # Banxico target interest rate
    "international_reserves": "SF43707",
    "m1": "SF311408",                   # Monetary aggregate M1
    "m2": "SF311418",                   # Monetary aggregate M2
}

BANXICO_BASE_URL = "https://www.banxico.org.mx/SieAPIRest/service/v1/series"

# --- INEGI (Indicators API) ---
# IMPORTANT: confirm each ID via INEGI's query builder before using it:
# https://www.inegi.org.mx/servicios/api_indicadores.html
INEGI_INDICATORS = {
    "quarterly_gdp": "735879",          # Gross Domestic Product, Quarterly
    "cpi": "910392",                    # General CPI, monthly, base 2018
    "unemployment_rate": "444603",      # Unemployment, monthly, base 2018
}

INEGI_BASE_URL = "https://www.inegi.org.mx/app/api/indicadores/desarrolladores/jsonxml/INDICATOR"

# --- Data paths ---
DATA_RAW_DIR = "data/raw"
DATA_PROCESSED_DIR = "data/processed"

# --- Historical reference window ---
# Starting from the Salinas administration. See README for comparability
# limitations in employment/informality data (ENOE only reliable since 2005).
HIST_START_DATE = "1988-01-01"