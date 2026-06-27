from pathlib import Path
import io
import json
import os

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
import pandas as pd


BASE_DIR = Path(__file__).resolve().parent
MPL_CONFIG_DIR = BASE_DIR / ".matplotlib"
MPL_CONFIG_DIR.mkdir(exist_ok=True)
os.environ.setdefault("MPLCONFIGDIR", str(MPL_CONFIG_DIR))
XDG_CACHE_DIR = BASE_DIR / ".cache"
XDG_CACHE_DIR.mkdir(exist_ok=True)
os.environ.setdefault("XDG_CACHE_HOME", str(XDG_CACHE_DIR))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt


app = FastAPI(title="EIA Real Grid Backtesting API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

EIA_BACKTESTS = {
    "2025": {
        "title": "2025 historical backtest",
        "title_zh": "2025 年历史回测",
        "dataset_path": BASE_DIR / "data" / "eia_ciso_2021_2025_generation_load.csv",
        "prediction_path": BASE_DIR / "data" / "eia_ciso_2025_predictions_from_2021_2024.csv",
        "metrics_path": BASE_DIR / "data" / "eia_ciso_2025_backtest_2021_2024_metrics.json",
        "training_window": "2021-01-01 to 2024-12-31",
        "evaluation_window": "2025-01-01 to 2025-12-31",
    },
    "2026": {
        "title": "2026 rolling evaluation",
        "title_zh": "2026 年滚动预测评估",
        "dataset_path": BASE_DIR / "data" / "eia_ciso_2021_2026_generation_load.csv",
        "prediction_path": BASE_DIR / "data" / "eia_ciso_2026_predictions_from_2021_2025.csv",
        "metrics_path": BASE_DIR / "data" / "eia_ciso_2026_backtest_2021_2025_metrics.json",
        "training_window": "2021-01-01 to 2025-12-31",
        "evaluation_window": "2026 published hours",
    },
}


def read_json_file(path):
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def summarize_time_series(path):
    if not path.exists():
        return None

    data = pd.read_csv(path, usecols=["DATE_TIME_LOCAL"])
    timestamps = pd.to_datetime(data["DATE_TIME_LOCAL"], errors="coerce").dropna()
    if timestamps.empty:
        return {"rows": int(len(data)), "start": None, "end": None}

    return {
        "rows": int(len(data)),
        "start": str(timestamps.min()),
        "end": str(timestamps.max()),
    }


def target_metric(metrics_data, target, metric_key="model"):
    target_data = metrics_data.get("targets", {}).get(target, {})
    metric = target_data.get(metric_key)
    if not metric:
        return None

    return {
        "mae": metric.get("mae"),
        "rmse": metric.get("rmse"),
        "mape_percent": metric.get("mape_percent"),
        "rows": metric.get("rows", target_data.get("actual_rows")),
    }


def build_eia_case_summary(case_id, case):
    metrics_data = read_json_file(case["metrics_path"])
    if metrics_data is None:
        return {
            "id": case_id,
            "title": case["title"],
            "title_zh": case["title_zh"],
            "available": False,
            "training_window": case["training_window"],
            "evaluation_window": case["evaluation_window"],
            "dataset": summarize_time_series(case["dataset_path"]),
            "predictions": summarize_time_series(case["prediction_path"]),
        }

    return {
        "id": case_id,
        "title": case["title"],
        "title_zh": case["title_zh"],
        "available": True,
        "training_window": case["training_window"],
        "evaluation_window": case["evaluation_window"],
        "dataset": summarize_time_series(case["dataset_path"]),
        "predictions": summarize_time_series(case["prediction_path"]),
        "features": metrics_data.get("features", []),
        "targets": {
            "load": {
                "label": "Load",
                "label_zh": "负荷",
                "model": target_metric(metrics_data, "LOAD_MW"),
            },
            "solar": {
                "label": "Solar generation",
                "label_zh": "太阳能发电",
                "model": target_metric(metrics_data, "SOLAR_MW"),
                "active_generation_model": target_metric(metrics_data, "SOLAR_MW", "active_generation_model"),
            },
            "wind": {
                "label": "Wind generation",
                "label_zh": "风电",
                "model": target_metric(metrics_data, "WIND_MW"),
            },
            "net_load": {
                "label": "Net load",
                "label_zh": "净负荷",
                "model": target_metric(metrics_data, "NET_LOAD_MW"),
            },
        },
    }


def plot_response():
    buffer = io.BytesIO()
    plt.tight_layout()
    plt.savefig(buffer, format="png")
    buffer.seek(0)
    plt.close()
    return Response(content=buffer.getvalue(), media_type="image/png")


app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")


@app.get("/")
async def read_index():
    return FileResponse(str(BASE_DIR / "static" / "index.html"))


@app.get("/health")
async def health_check():
    return {
        "status": "ok",
        "mode": "eia_real_grid_backtest",
        "real_data_only": True,
        "source": "EIA Open Data electricity API",
        "source_zh": "EIA Open Data 电力 API",
        "cases": [case_id for case_id in EIA_BACKTESTS],
    }


@app.get("/eia/backtests")
async def get_eia_backtests():
    return {
        "source": "EIA Open Data electricity API",
        "source_zh": "EIA Open Data 电力 API",
        "description": "Hourly real grid load, solar generation, wind generation, and net-load fields are used for multi-year backtesting.",
        "description_zh": "使用小时级真实电网负荷、太阳能发电、风电和净负荷字段，完成多年时间切分回测。",
        "cases": [build_eia_case_summary(case_id, case) for case_id, case in EIA_BACKTESTS.items()],
    }


@app.get("/plot/eia_backtest")
async def get_eia_backtest_plot(period: str = "2025", target: str = "net_load"):
    case = EIA_BACKTESTS.get(period)
    if case is None:
        raise HTTPException(status_code=404, detail="Unknown EIA backtest period.")
    if not case["prediction_path"].exists():
        raise HTTPException(status_code=404, detail="EIA prediction file is not available.")

    target_columns = {
        "load": ("LOAD_MW", "PREDICTED_LOAD_MW", "Load demand"),
        "solar": ("SOLAR_MW", "PREDICTED_SOLAR_MW", "Solar generation"),
        "wind": ("WIND_MW", "PREDICTED_WIND_MW", "Wind generation"),
        "net_load": ("NET_LOAD_MW", "PREDICTED_NET_LOAD_MW", "Net load"),
    }
    if target not in target_columns:
        raise HTTPException(status_code=404, detail="Unknown EIA target.")

    actual_col, predicted_col, title = target_columns[target]
    try:
        data = pd.read_csv(case["prediction_path"])
        data["DATE_TIME_LOCAL"] = pd.to_datetime(data["DATE_TIME_LOCAL"], errors="coerce")
        data = data.dropna(subset=["DATE_TIME_LOCAL", actual_col, predicted_col]).sort_values("DATE_TIME_LOCAL")
        if data.empty:
            raise HTTPException(status_code=404, detail="No plottable EIA rows.")

        plot_df = data.tail(336)
        plt.figure(figsize=(15, 8))
        plt.plot(plot_df["DATE_TIME_LOCAL"], plot_df[actual_col], label="Actual", color="#0f172a", linewidth=2)
        plt.plot(
            plot_df["DATE_TIME_LOCAL"],
            plot_df[predicted_col],
            label="Predicted",
            color="#1769aa",
            linewidth=2,
            linestyle="--",
        )
        plt.title(f"EIA CISO {period} {title}: Actual vs Predicted", fontsize=16, fontweight="bold")
        plt.ylabel("Power (MW)")
        plt.xlabel("Local time")
        plt.legend()
        plt.grid(True, alpha=0.3)
        plt.xticks(rotation=35)
        return plot_response()
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"EIA plot generation failed: {exc}") from exc


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
