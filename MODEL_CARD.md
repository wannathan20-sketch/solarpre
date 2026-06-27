# Model Card: EIA Real Grid Backtesting Baseline

## Purpose

This project is a portfolio-oriented forecasting and backtesting baseline using real public grid data from the EIA Open Data electricity API.

The intended experiments are:

- Train on 2021-2024 real hourly data and evaluate on 2025 actuals.
- Train on 2021-2025 real hourly data and evaluate on published 2026 actuals.

## Data

Primary source: EIA Open Data electricity API.

Default respondent: `CISO`, the California ISO balancing authority/RTO identifier used by EIA.

Main fields:

- `LOAD_MW`: actual system load
- `LOAD_FORECAST_MW`: load forecast, when available
- `SOLAR_MW`: actual solar generation
- `WIND_MW`: actual wind generation
- `GENERATION_MW`: solar plus wind generation
- `NET_LOAD_MW`: load minus solar and wind
- `SOLAR_SHARE_PERCENT`: solar generation divided by load

The current EIA route intentionally replaces the earlier formula-derived regional demonstration data as the primary project narrative.

## Targets

The backtest trains separate XGBoost regression models for:

- `LOAD_MW`
- `SOLAR_MW`
- `WIND_MW`
- `NET_LOAD_MW`, derived from the individual predictions

## Features

The baseline uses calendar features:

- hour
- month
- day of week
- weekend flag
- season

It also uses available public forecast columns such as `LOAD_FORECAST_MW` when present in the downloaded EIA dataset.

## Evaluation

The evaluation is chronological:

- 2025 backtest: train through 2024, evaluate future 2025 rows.
- 2026 rolling evaluation: train through 2025, evaluate published 2026 rows.

Metrics:

- MAE
- RMSE
- MAPE

Current generated datasets:

- `solar/data/eia_ciso_2021_2025_generation_load.csv`: 43,824 rows, 2021-01-01 to 2025-12-31
- `solar/data/eia_ciso_2021_2026_generation_load.csv`: 47,472 rows, 2021-01-01 to 2026-06-01
- `solar/data/eia_ciso_2025_predictions_from_2021_2024.csv`: 8,712 prediction rows
- `solar/data/eia_ciso_2026_predictions_from_2021_2025.csv`: 3,625 prediction rows

Metric JSON files:

- `solar/data/eia_ciso_2025_backtest_2021_2024_metrics.json`
- `solar/data/eia_ciso_2026_backtest_2021_2025_metrics.json`

Current MAPE results against simple baselines:

| Experiment | Target | Model | Previous day | Previous week | EIA load forecast |
| --- | --- | ---: | ---: | ---: | ---: |
| 2021-2024 to 2025 | Load | 4.84% | 4.89% | 5.86% | 8.17% |
| 2021-2024 to 2025 | Solar | 661.51% | 73.00% | 98.14% | - |
| 2021-2024 to 2025 | Solar active generation | 77.13% | 18.44% | 29.11% | - |
| 2021-2024 to 2025 | Wind | 66.01% | 65.04% | 92.75% | - |
| 2021-2024 to 2025 | Net load | 16.38% | 13.25% | 18.25% | - |
| 2021-2025 to 2026 | Load | 6.84% | 4.98% | 5.74% | 9.72% |
| 2021-2025 to 2026 | Solar | 352.53% | 41.09% | 47.75% | - |
| 2021-2025 to 2026 | Solar active generation | 49.81% | 20.59% | 32.84% | - |
| 2021-2025 to 2026 | Wind | 161.52% | 95.88% | 113.86% | - |
| 2021-2025 to 2026 | Net load | 11.85% | 12.31% | 15.73% | - |

The load model improves on the EIA load forecast baseline. The renewable-generation models do not yet beat simple lag baselines, which is an important limitation rather than a hidden result.

Full-period solar MAPE is inflated by night and near-zero generation hours, so active-generation metrics are reported separately for rows with actual solar above 100 MW.

## Limitations

- EIA `CISO` data represents the California grid, not a Chinese regional grid.
- The baseline is not a production dispatch model.
- Weather forecasts, holidays, outages, curtailment, prices, and grid constraints are not yet included.
- Solar and wind behavior can be difficult to predict from calendar and public forecast fields alone.
- The project currently emphasizes transparent time-split evaluation over maximum model accuracy.
