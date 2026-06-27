# Deployment Guide

This project deploys as a Python/FastAPI web service. The deployable application is in the `solar/` directory.

## Local Run

On macOS, XGBoost may need the OpenMP runtime:

```bash
brew install libomp
```

```bash
cd /Users/wanna/solar_pred/solar-main
python3 -m venv .venv
source .venv/bin/activate
pip install -r solar/requirements.txt

cd solar
uvicorn app:app --host 0.0.0.0 --port 8000 --reload
```

Open:

```text
http://localhost:8000
```

Useful checks:

```text
http://localhost:8000/health
http://localhost:8000/eia/backtests
http://localhost:8000/docs
```

## EIA API Key

Downloading fresh EIA data requires:

```bash
export EIA_API_KEY="your EIA API key"
```

The deployed service can read already-generated CSV/JSON files without the key. Configure `EIA_API_KEY` in Zeabur only if the deployment will download data at runtime.

## Zeabur Deployment

The repository includes `nixpacks.toml` and `.python-version` for Zeabur. Zeabur can deploy the project as a Python web service from the repository root while the FastAPI application stays in the `solar/` directory.

The Nixpacks settings are:

| Setting | Value |
| --- | --- |
| Runtime | Python 3.11 |
| Build Command | `pip install -r solar/requirements.txt` |
| Start Command | `cd solar && uvicorn app:app --host 0.0.0.0 --port $PORT` |

Steps:

1. Push this repository to GitHub.
2. Open Zeabur and create a new project.
3. Connect the GitHub repository.
4. Add the repository as a service.
5. Let Zeabur use the included `nixpacks.toml` configuration.
6. Wait for the build and open the deployed domain.

## Post-Deployment Checklist

- `/` loads the EIA backtesting dashboard.
- `/health` returns `mode: eia_real_grid_backtest`.
- `/eia/backtests` returns the 2025/2026 EIA experiment summaries.
- `/plot/eia_backtest?period=2025&target=net_load` returns a PNG chart after prediction files are generated.

## Notes

- Zeabur injects the `PORT` environment variable at runtime; the start command uses it directly.
- Keep large generated EIA data files in Release assets, object storage, or data versioning if the repository becomes too large.
