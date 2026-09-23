import pandas as pd
from src.analysis.surrogates import gaussian_detrend, select_arma_order
from statsmodels.tsa.arima.model import ARIMA

panel = pd.read_csv('data/processed/panel_long.csv', parse_dates=['date'])
series_df = panel[panel.series_key == 'm1'].dropna(subset=['value']).sort_values('date')
cutoff = series_df['date'].max() - pd.DateOffset(years=10)
raw = series_df[series_df['date'] >= cutoff]['value'].to_numpy()

residuals = gaussian_detrend(raw)
result = select_arma_order(residuals)
print("Orden elegido:", result['order'])
print("AICc del ganador:", result['aicc'])
print("¿Ljung-Box adecuado?:", result['adequate'], "p=", result['ljung_box_p'])

# Compara contra el modelo simple, para ver si la ganancia es real o marginal
simple = ARIMA(residuals, order=(1, 0, 1), trend="n").fit()
k_simple = 1 + 1 + 1
aicc_simple = simple.aic + (2 * k_simple * (k_simple + 1)) / (len(residuals) - k_simple - 1)
print("AICc de ARMA(1,1) para comparar:", aicc_simple)
print("Diferencia (ganador - simple):", result['aicc'] - aicc_simple)