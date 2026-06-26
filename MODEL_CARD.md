# Model Card

## Model Purpose

The project contains two recruiting-oriented baseline models for representative regional power-grid service-area cities:

- Stage 1 estimates hourly regional photovoltaic output.
- Stage 2 estimates hourly regional load demand and supports PV-vs-load dispatch analysis.
- Stage 3 uses rule-based storage dispatch logic to recommend charge, discharge, or standby actions.

It is intended for portfolio demonstration, renewable forecasting discussion, generation-load-storage analytics, and grid dispatch interview storytelling.

## Model Type

- Algorithm: XGBoost Regressor
- Frameworks: XGBoost, scikit-learn, pandas
- Solar artifact: `solar/south_china_solar_model.joblib`
- Load artifact: `solar/south_china_load_model.joblib`
- Legacy artifact: `solar/solar_model.joblib`
- Storage layer: deterministic heuristic logic in `solar/app.py`

## Data Source

Primary source: NASA POWER hourly API.

Regions:

- Guangdong - Guangzhou
- Guangdong - Shenzhen
- Guangxi - Nanning
- Yunnan - Kunming
- Guizhou - Guiyang
- Hainan - Haikou

Weather and irradiance variables:

- `T2M`
- `RH2M`
- `WS2M`
- `ALLSKY_SFC_SW_DWN`

Generated dataset:

- File: `solar/data/south_china_solar_power.csv`
- Rows: 52,704
- Period: 2024-01-01 to 2024-12-31
- Granularity: hourly

Second-stage generated dataset:

- File: `solar/data/south_china_load_power.csv`
- Rows: 52,704
- Period: 2024-01-01 to 2024-12-31
- Granularity: hourly

## Target

- Target: `SOLAR_POWER_MW`
- Unit: MW

The target is generated from a transparent PV baseline formula using:

- Solar irradiance
- Estimated module temperature
- Demo installed capacity
- Performance ratio
- Temperature derating

This is not official utility operating data.

Second-stage target:

- Target: `REGIONAL_LOAD_MW`
- Unit: MW

The load target is generated from a transparent regional demand baseline using:

- Hour-of-day load shape
- Weekday/weekend pattern
- Summer cooling and winter heating effects
- Temperature, humidity, and wind-speed stress factors
- Demo regional peak-load assumptions

This is not official utility load or dispatch data.

## Inputs

The public regional prediction API accepts:

- `region_id`
- `DATE_TIME`
- `AMBIENT_TEMPERATURE`
- `RELATIVE_HUMIDITY`
- `WIND_SPEED`
- `IRRADIATION`
- Optional `MODULE_TEMPERATURE`

Engineered model features include:

- Calendar features: `HOUR`, `MONTH`, `IF_DAYTIME`, `DAY_OF_WEEK`, `IS_WEEKEND`, `SEASON`
- Location/capacity features: `REGION_CODE`, `LATITUDE`, `LONGITUDE`, `CAPACITY_MW`
- Weather features: `AMBIENT_TEMPERATURE`, `RELATIVE_HUMIDITY`, `WIND_SPEED`, `IRRADIATION`, `MODULE_TEMPERATURE`
- Interaction features: `MODULE_AMBIENT_DIFF`, `TEMPERATURE_IRRADIATION`, `IRRADIATION_CAPACITY`, `WIND_IRRADIATION`

The load model uses similar calendar, location, and weather features, plus `PEAK_LOAD_MW`.

The storage dispatch layer uses:

- PV prediction in MW
- Load prediction in MW
- Region storage power rating in MW
- Region storage energy capacity in MWh
- Current SOC percentage
- Hour-of-day and load-ratio heuristics

## Evaluation

The training script uses 5-fold cross-validation with R2 scoring.

Current regional model result:

- Cross-validation R2: 1.0000 +/- 0.0000
- Stage 2 load model cross-validation R2: 0.9996 +/- 0.0000

These scores are expected because both current targets are formula-derived from the same time and weather drivers. They should be treated as baseline pipeline validation scores, not proof of real-world dispatch forecasting accuracy.

The third-stage storage layer is not evaluated as a learned model. It is an explainable decision rule intended to demonstrate how PV and load predictions can feed into storage dispatch assistance.

## Limitations

- No official utility measured PV output or dispatch data is included.
- No official utility measured load data is included.
- Demo installed capacities, demo peak-load values, and demo storage ratings are assumptions.
- NASA POWER data is gridded reanalysis/satellite-derived data, not plant-level sensor data.
- The models have not been validated against measured PV generation or regional load.
- The storage dispatch layer is not a production control strategy and does not perform power-flow, unit-commitment, security-constrained dispatch, or market optimization.
- It is a recruiting portfolio baseline; later stages should add measured generation, measured load, uncertainty evaluation, constrained optimization, and storage/curtailment decision validation.
