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

Metric JSON files are expected at:

- `solar/data/eia_ciso_2025_backtest_2021_2024_metrics.json`
- `solar/data/eia_ciso_2026_backtest_2021_2025_metrics.json`

These files are generated after downloading EIA data with an `EIA_API_KEY`.

## Limitations

- EIA `CISO` data represents the California grid, not a Chinese regional grid.
- The baseline is not a production dispatch model.
- Weather forecasts, holidays, outages, curtailment, prices, and grid constraints are not yet included.
- Solar and wind behavior can be difficult to predict from calendar and public forecast fields alone.
- The project currently emphasizes transparent time-split evaluation over maximum model accuracy.
