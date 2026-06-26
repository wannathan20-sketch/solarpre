# Regional Renewable Generation Forecasting and Grid Dispatch Dashboard

区域新能源发电预测与电网调度辅助平台

A personal machine learning web project tailored for regional power-grid recruiting scenarios. The current version uses NASA POWER meteorological and solar irradiance data for representative South China and Southwest China cities, estimates regional photovoltaic generation, adds a weather-driven regional load baseline, and serves grid dispatch assistance through a FastAPI dashboard.

## Why This Version

The original project predicted a single solar plant's daily yield from Kaggle plant operation data. This version shifts the story toward grid-company work:

- Regional renewable power forecasting
- Weather-driven solar output and load-demand estimation
- Generation-load-storage analytics foundation
- Dispatch-support dashboard prototype

## What It Does

- Fetches hourly NASA POWER weather and solar irradiance data for Guangdong, Guangxi, Yunnan, Guizhou, and Hainan representative cities.
- Builds a regional solar output dataset with demo installed capacity assumptions.
- Trains an XGBoost model to estimate hourly regional photovoltaic output in MW.
- Builds a second-stage regional load-demand baseline from time, weather, humidity, wind, and regional peak-load assumptions.
- Trains a second XGBoost model to estimate hourly regional load demand in MW.
- Adds a third-stage rule-based storage dispatch layer for charge/discharge/standby recommendations.
- Adds a CAISO real public grid-data validation path for 2025 historical backtesting and 2026 rolling evaluation.
- Exposes FastAPI endpoints for regional PV prediction, load prediction, generation-load balance, storage dispatch, CAISO backtest summaries, feature importance, trend charts, heatmaps, load-balance plots, and storage strategy plots.
- Serves a lightweight web UI for manual grid dispatch-support scenarios.

## Tech Stack

| Layer | Tools |
| --- | --- |
| Data source | NASA POWER hourly API |
| Backend API | FastAPI, Uvicorn |
| Machine learning | XGBoost, scikit-learn, pandas, NumPy, joblib |
| Visualization | Matplotlib, Seaborn |
| Frontend | HTML, CSS, vanilla JavaScript |
| Deployment | Zeabur |

## Project Structure

```text
solar-main/
|-- solar/
|   |-- app.py                              # FastAPI app and API routes
|   |-- regions.py                          # Representative regional grid scenarios
|   |-- solar_predictor.py                  # Model wrapper and feature engineering
|   |-- train_regional_model.py             # Trains the regional solar model
|   |-- train_load_model.py                 # Trains the second-stage regional load model
|   |-- train_model.py                      # Legacy Kaggle plant training script
|   |-- data_sources/nasa_power.py          # NASA POWER data fetcher
|   |-- data_sources/caiso_oasis.py         # CAISO OASIS real grid data fetcher
|   |-- data_sources/caiso_batch_download.py # Resumable monthly CAISO downloader
|   |-- data/south_china_solar_power.csv    # Generated regional dataset
|   |-- data/south_china_load_power.csv     # Generated second-stage generation-load dataset
|   |-- data/caiso_sample_with_forecast.csv # Sample real CAISO load/solar/wind data
|   |-- south_china_solar_model.joblib      # Regional model artifact
|   |-- south_china_load_model.joblib       # Regional load model artifact
|   |-- solar_model.joblib                  # Legacy plant model artifact
|   |-- static/index.html                   # Web UI
|   `-- requirements.txt                    # Python dependencies
|-- MODEL_CARD.md                           # Model and data limitations
|-- DEPLOYMENT.md                           # Deployment notes
|-- legacy/spring-boot-shell/               # Early Spring Boot experiment, not required
|-- .python-version                         # Python version hint for Zeabur/Nixpacks
|-- nixpacks.toml                           # Zeabur/Nixpacks deployment config
`-- requirements.txt
```

The production path is the Python/FastAPI app in `solar/`. The app loads `south_china_solar_model.joblib` for renewable output forecasting and `south_china_load_model.joblib` for the second-stage load-demand module when present. It falls back to the legacy plant model only if the regional solar model is missing.

## Regional Data

Representative regions:

- Guangdong - Guangzhou
- Guangdong - Shenzhen
- Guangxi - Nanning
- Yunnan - Kunming
- Guizhou - Guiyang
- Hainan - Haikou

NASA POWER parameters:

- `T2M`: temperature at 2 meters
- `RH2M`: relative humidity at 2 meters
- `WS2M`: wind speed at 2 meters
- `ALLSKY_SFC_SW_DWN`: all-sky surface shortwave downward irradiance

The generated solar dataset has 52,704 hourly rows for 2024 across 6 representative regions. The target `SOLAR_POWER_MW` is estimated with a simple PV baseline formula using irradiance, module temperature, performance ratio, and demo installed capacity. It is a portfolio baseline, not official utility operating data.

## Stage 2: Load Forecast and Generation-Load Balance

The second stage adds a regional load-demand module so the dashboard can answer a more grid-oriented question: after expected PV output, how much net load still needs to be supplied by the grid and other flexible resources?

The generated load target `REGIONAL_LOAD_MW` is a transparent demo baseline derived from:

- Hour-of-day load shape
- Weekday/weekend demand pattern
- Summer cooling and winter heating effects
- Temperature, humidity, and wind-speed stress factors
- Demo regional peak-load assumptions

This is not measured utility load data. It is a recruiting-oriented prototype that demonstrates the generation-load modeling pipeline. If real SCADA, EMS, AMI, or dispatch load data becomes available, the target column can be replaced while keeping the data pipeline, model service, and dashboard structure.

## Stage 3: Storage Dispatch Assistance

The third stage adds a storage dispatch assistance layer on top of the PV and load predictions. It uses transparent storage assumptions for each representative region:

- Storage power rating in MW
- Storage energy capacity in MWh
- Current state of charge entered from the dashboard
- Operating reserve and maximum charge bounds

The decision layer returns:

- Recommended action: charge, discharge, or standby
- Recommended storage power
- Net load before and after storage
- Peak-shaving contribution
- SOC change
- Curtailment/consumption risk hint
- A dispatch-oriented explanation

This is a heuristic dispatch-assistance layer, not a production storage control algorithm. It is designed to show how renewable generation forecasting and load forecasting can feed into storage charge/discharge decisions.

## Public Real-Data Extension: CAISO

The project now includes a CAISO OASIS data connector for real public grid data. CAISO is useful for portfolio validation because it publishes actual load, day-ahead load forecasts, actual solar/wind generation, and day-ahead solar/wind forecasts.

The connector can download:

- `LOAD_MW`: actual system load
- `LOAD_FORECAST_MW`: day-ahead load forecast
- `SOLAR_MW`: actual solar generation
- `SOLAR_FORECAST_MW`: day-ahead solar forecast
- `WIND_MW`: actual wind generation
- `WIND_FORECAST_MW`: day-ahead wind forecast
- `NET_LOAD_MW`: load minus solar and wind
- `SOLAR_SHARE_PERCENT`: solar generation share of load

Fetch a one-day sample:

```bash
python3 solar/data_sources/caiso_oasis.py \
  --start 2024-06-01 \
  --end 2024-06-01 \
  --output solar/data/caiso_sample_with_forecast.csv
```

Fetch a longer backtest window:

```bash
python3 solar/data_sources/caiso_batch_download.py \
  --start 2024-01-01 \
  --end 2024-12-31 \
  --output-dir solar/data/caiso_monthly_2024 \
  --combined-output solar/data/caiso_2024_generation_load.csv \
  --chunk-days 7
```

Recommended backtest framing:

- Train on historical CAISO actual load and solar/wind generation.
- Use day-ahead CAISO forecasts as a baseline.
- Compare model predictions against actual values using MAE, RMSE, and MAPE.
- Analyze net-load ramps and storage charge/discharge opportunities.

Note: CAISO actual solar values may contain small negative night-time values due to market/reporting adjustments. Keep them for data authenticity, or clip them to zero when training a physical solar generation model.

Train on pre-2025 data and backtest against real 2025 data:

```bash
python3 solar/data_sources/caiso_batch_download.py \
  --start 2024-01-01 \
  --end 2025-12-31 \
  --output-dir solar/data/caiso_monthly_2024_2025 \
  --combined-output solar/data/caiso_2024_2025_generation_load.csv \
  --chunk-days 7

python3 solar/train_caiso_backtest.py \
  --input solar/data/caiso_2024_2025_generation_load.csv \
  --train-start 2024-01-01 \
  --train-end 2024-12-31 \
  --predict-start 2025-01-01 \
  --predict-end 2025-12-31 \
  --output solar/data/caiso_2025_predictions.csv \
  --metrics-output solar/data/caiso_2025_backtest_metrics.json
```

Train through 2025 and predict available 2026 rows:

```bash
python3 solar/data_sources/caiso_batch_download.py \
  --start 2024-01-01 \
  --end 2026-06-01 \
  --output-dir solar/data/caiso_monthly_2024_2026 \
  --combined-output solar/data/caiso_2024_2026_generation_load.csv \
  --chunk-days 7

python3 solar/train_caiso_backtest.py \
  --input solar/data/caiso_2024_2026_generation_load.csv \
  --train-start 2024-01-01 \
  --train-end 2025-12-31 \
  --predict-start 2026-01-01 \
  --predict-end 2026-06-01 \
  --output solar/data/caiso_2026_predictions.csv \
  --metrics-output solar/data/caiso_2026_metrics.json
```

For future dates beyond the latest actual data, CAISO day-ahead forecast columns are only available once CAISO publishes them. To forecast farther into the future, add weather forecast features from Open-Meteo or another forecast provider.

CAISO note: the `SLD_REN_FCST` OASIS report used here provides separated solar and wind actual/forecast data reliably for recent years. If you need a longer pre-2024 history, use CAISO's historical wind/solar summary or EIA hourly grid data, but those sources may use different renewable aggregation rules.

### CAISO Backtest Results

The current checked-in CAISO real-data run includes:

| File | Window | Rows | Purpose |
| --- | --- | ---: | --- |
| `solar/data/caiso_2024_2025_generation_load.csv` | 2024-01-01 to 2025-12-31 | 17,544 | Training + 2025 backtest dataset |
| `solar/data/caiso_2025_predictions.csv` | 2025-01-01 to 2025-12-31 | 8,760 | 2025 hourly predictions and actuals |
| `solar/data/caiso_2025_backtest_metrics.json` | 2025 full year | - | 2025 backtest metrics |
| `solar/data/caiso_2024_2026_generation_load.csv` | 2024-01-01 to 2026-06-01 | 21,191 | Training + 2026 rolling evaluation dataset |
| `solar/data/caiso_2026_predictions.csv` | 2026-01-01 to 2026-06-01 | 3,647 | 2026 hourly predictions and actuals available so far |
| `solar/data/caiso_2026_metrics.json` | 2026 year-to-date | - | 2026 rolling evaluation metrics |

2025 backtest, trained on 2024 and tested against real 2025 CAISO actuals:

| Target | Model MAE | Model RMSE | Model MAPE | CAISO day-ahead baseline MAE | Baseline RMSE | Baseline MAPE |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Load MW | 736.46 | 1,050.73 | 2.80% | 1,897.64 | 2,910.73 | 7.31% |
| Solar MW | 506.64 | 918.96 | 164.09% | 748.80 | 1,467.58 | 85.63% |
| Solar MW, active generation only | 894.27 | 1,237.25 | 18.61% | 1,324.17 | 1,976.45 | 23.14% |
| Wind MW | 250.70 | 338.99 | 47.84% | 242.53 | 336.24 | 38.32% |
| Net Load MW | 846.17 | 1,178.54 | 6.39% | - | - | - |

2026 rolling evaluation, trained on 2024-2025 and evaluated on available 2026 actuals through 2026-06-01:

| Target | Model MAE | Model RMSE | Model MAPE | CAISO day-ahead baseline MAE | Baseline RMSE | Baseline MAPE |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Load MW | 1,032.77 | 1,612.05 | 4.07% | 2,429.99 | 3,781.53 | 9.68% |
| Solar MW | 725.17 | 1,345.20 | 81.26% | 1,215.06 | 2,389.52 | 72.37% |
| Solar MW, active generation only | 1,386.05 | 1,879.39 | 16.41% | 2,329.69 | 3,338.85 | 24.76% |
| Wind MW | 244.25 | 340.04 | 68.86% | 250.83 | 363.62 | 60.11% |
| Net Load MW | 1,098.19 | 1,700.47 | 8.80% | - | - | - |

Interpretation:

- Load forecasting is the strongest part of the current real-data pipeline; the model improves substantially over the CAISO day-ahead baseline on both 2025 and 2026 windows.
- Solar forecasting improves MAE and RMSE over the day-ahead baseline. Full-period solar MAPE is inflated by night-time and low-generation hours where the denominator is close to zero, so the active-generation rows are the better interview metric.
- Wind forecasting is close to the day-ahead baseline and slightly worse by MAPE. This is expected because wind is more volatile and the current model only uses calendar plus CAISO forecast features.
- Net-load prediction is now measurable against real data and can directly support the storage charge/discharge analysis.

## Local Setup

Use Python 3.11 if possible.

On macOS, install the OpenMP runtime required by XGBoost:

```bash
brew install libomp
```

```bash
cd /Users/wanna/solar_pred/solar-main
python3 -m venv .venv
source .venv/bin/activate
pip install -r solar/requirements.txt
```

Run the app:

```bash
cd solar
uvicorn app:app --host 0.0.0.0 --port 8000 --reload
```

Open:

```text
http://localhost:8000
```

## Rebuild Data and Model

Fetch NASA POWER data:

```bash
cd /Users/wanna/solar_pred/solar-main
python3 solar/data_sources/nasa_power.py --start 20240101 --end 20241231
```

Fetch CAISO real public grid data:

```bash
python3 solar/data_sources/caiso_oasis.py --start 2024-06-01 --end 2024-06-01
```

Train the regional model:

```bash
python3 solar/train_regional_model.py
```

Train the second-stage regional load model:

```bash
python3 solar/train_load_model.py
```

## API Overview

| Endpoint | Method | Purpose |
| --- | --- | --- |
| `/` | GET | Web interface |
| `/health` | GET | Service, model mode, and row-count health check |
| `/regions` | GET | Representative regional scenario metadata |
| `/predict_region` | POST | Regional solar output prediction |
| `/predict_load` | POST | Regional load-demand prediction |
| `/predict_dispatch` | POST | Combined PV generation, load demand, net load, and dispatch hint |
| `/predict_storage_dispatch` | POST | Storage charge/discharge decision based on PV, load, and SOC |
| `/features` | GET | Model feature list |
| `/caiso/backtests` | GET | CAISO 2025/2026 real-data backtest summary |
| `/feature_importance` | GET | Feature importance values |
| `/plot/timeseries` | GET | Regional actual-estimate vs model prediction trend |
| `/plot/heatmap` | GET | Regional solar output heatmap |
| `/plot/load_balance` | GET | PV generation vs load demand and net-load chart |
| `/plot/storage_strategy` | GET | PV, load, net-load-after-storage, storage power, and SOC chart |
| `/plot/caiso_backtest?period=2025&target=net_load` | GET | CAISO actual-vs-predicted backtest chart |

Example regional prediction request:

```json
{
  "region_id": "guangdong_guangzhou",
  "DATE_TIME": "2024-07-01 12:00:00",
  "AMBIENT_TEMPERATURE": 32.0,
  "RELATIVE_HUMIDITY": 72.0,
  "WIND_SPEED": 2.6,
  "IRRADIATION": 760.0,
  "storage_soc_percent": 50.0
}
```

Example response:

```json
{
  "status": "success",
  "mode": "regional_solar",
  "prediction_mw": 279.27,
  "target": "SOLAR_POWER_MW"
}
```

Example dispatch response fields:

```json
{
  "status": "success",
  "mode": "generation_load_dispatch",
  "solar_prediction_mw": 279.27,
  "load_prediction_mw": 6810.42,
  "dispatch_assessment": {
    "net_load_mw": 6531.15,
    "solar_share_percent": 4.10,
    "supply_level": "low",
    "ramp_risk": "low",
    "recommendation": "PV contribution is limited..."
  },
  "storage_dispatch": {
    "action": "charge",
    "storage_power_mw": 69.82,
    "net_load_after_storage_mw": 6600.97,
    "peak_shaving_mw": 0.0,
    "next_soc_percent": 60.04,
    "curtailment_risk": "low"
  }
}
```

## Current Limitations

- `SOLAR_POWER_MW` is estimated from public weather/irradiance data and a transparent PV baseline formula, not measured utility dispatch data.
- `REGIONAL_LOAD_MW` is also a transparent weather/time baseline, not measured utility load data.
- Region capacities, peak-load values, and storage ratings are demo assumptions for portfolio modeling.
- The current PV and load targets are formula-derived; production use would require real measured PV output, load, and dispatch context data where licensing permits.
- The storage dispatch layer is rule-based and intended for explainable prototype analysis, not automatic production control.
- The UI is intentionally lightweight and does not include scenario history, batch upload, or confidence intervals yet.

## Next Improvements

- Replace the demo load baseline with public benchmark load data or licensed measured regional load data.
- Replace rule-based storage recommendations with constrained optimization, model predictive control, or probabilistic dispatch under uncertainty.
- Add Pydantic request schemas and automated API tests.
