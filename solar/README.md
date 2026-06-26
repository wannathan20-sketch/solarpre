# Solar App Directory

This directory contains the FastAPI app, regional solar model, regional load model, storage dispatch logic, frontend, NASA POWER data pipeline, and generated regional generation-load datasets.

Run locally from this directory:

```bash
pip install -r requirements.txt
uvicorn app:app --host 0.0.0.0 --port 8000 --reload
```

Rebuild the first-stage regional dataset and model:

```bash
python3 data_sources/nasa_power.py --start 20240101 --end 20241231
python3 train_regional_model.py
```

Build the second-stage regional load-demand model:

```bash
python3 train_load_model.py
```

The third-stage storage dispatch layer is rule-based and runs inside `app.py`; it does not require a separate training step.

Fetch a real public CAISO load/solar/wind sample:

```bash
python3 data_sources/caiso_oasis.py --start 2024-06-01 --end 2024-06-01
```

Download a resumable monthly CAISO backtest dataset:

```bash
python3 data_sources/caiso_batch_download.py \
  --start 2024-01-01 \
  --end 2025-12-31 \
  --output-dir data/caiso_monthly_2024_2025 \
  --combined-output data/caiso_2024_2025_generation_load.csv \
  --chunk-days 7
```

Backtest CAISO predictions:

```bash
python3 train_caiso_backtest.py \
  --input data/caiso_2024_2025_generation_load.csv \
  --train-start 2024-01-01 \
  --train-end 2024-12-31 \
  --predict-start 2025-01-01 \
  --predict-end 2025-12-31
```

Run the checked-in 2026 rolling evaluation:

```bash
python3 train_caiso_backtest.py \
  --input data/caiso_2024_2026_generation_load.csv \
  --train-start 2024-01-01 \
  --train-end 2025-12-31 \
  --predict-start 2026-01-01 \
  --predict-end 2026-06-01 \
  --output data/caiso_2026_predictions.csv \
  --metrics-output data/caiso_2026_metrics.json
```

Then open `http://localhost:8000`.

The dashboard includes a CAISO real-data validation view. Current checked-in results:

- 2025 historical backtest: load MAPE 2.80%, net-load MAPE 6.39%, solar active-generation MAPE 18.61%.
- 2026 rolling evaluation through 2026-06-01: load MAPE 4.07%, net-load MAPE 8.80%, solar active-generation MAPE 16.41%.

For the full project overview, setup notes, API documentation, and limitations, see the root `README.md` and `MODEL_CARD.md`.
