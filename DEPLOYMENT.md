# Deployment Guide

This project is ready to run as a Python web service. The deployable application is in the `solar/` directory.

## Local Run

On macOS, XGBoost needs the OpenMP runtime:

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
http://localhost:8000/docs
```

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

- `/` loads the web UI.
- `/health` returns `status: ok`.
- `/regions` returns representative regional scenarios.
- `/features` returns the saved model feature list.
- `/predict_region` returns a numeric MW prediction for a sample payload.
- `/plot/timeseries` returns a PNG chart.
- `/plot/heatmap` returns a PNG chart.

## Notes

- Zeabur injects the `PORT` environment variable at runtime; the start command uses it directly.
- The CSV files and model artifact are included for demo convenience.
- For a larger production deployment, move data/model artifacts to object storage and load them at startup.
