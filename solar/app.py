from pathlib import Path
import io
import json
import os

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
import pandas as pd

from regions import REGION_BY_ID, SOUTHERN_GRID_REGIONS
from schemas import LegacyPredictionRequest, RegionalPredictionRequest, payload_to_dict
from solar_predictor import Solar_Predictor
from storage_dispatch import optimize_storage_step

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
import seaborn as sns


app = FastAPI(title="Solar Power Generation Forecast API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

REGIONAL_MODEL_PATH = BASE_DIR / "south_china_solar_model.joblib"
LOAD_MODEL_PATH = BASE_DIR / "south_china_load_model.joblib"
LEGACY_MODEL_PATH = BASE_DIR / "solar_model.joblib"
REGIONAL_DATA_PATH = BASE_DIR / "data" / "south_china_solar_power.csv"
LOAD_DATA_PATH = BASE_DIR / "data" / "south_china_load_power.csv"
CAISO_BACKTESTS = {
    "2025": {
        "title": "2025 historical backtest",
        "title_zh": "2025 年历史回测",
        "dataset_path": BASE_DIR / "data" / "caiso_2024_2025_generation_load.csv",
        "prediction_path": BASE_DIR / "data" / "caiso_2025_predictions.csv",
        "metrics_path": BASE_DIR / "data" / "caiso_2025_backtest_metrics.json",
        "training_window": "2024-01-01 to 2024-12-31",
        "evaluation_window": "2025-01-01 to 2025-12-31",
    },
    "2026": {
        "title": "2026 rolling evaluation",
        "title_zh": "2026 年滚动预测评估",
        "dataset_path": BASE_DIR / "data" / "caiso_2024_2026_generation_load.csv",
        "prediction_path": BASE_DIR / "data" / "caiso_2026_predictions.csv",
        "metrics_path": BASE_DIR / "data" / "caiso_2026_metrics.json",
        "training_window": "2024-01-01 to 2025-12-31",
        "evaluation_window": "2026-01-01 to 2026-06-01",
    },
}

model_path = REGIONAL_MODEL_PATH if REGIONAL_MODEL_PATH.exists() else LEGACY_MODEL_PATH
model = Solar_Predictor.load_model(str(model_path))
MODEL_MODE = "regional_solar" if model_path == REGIONAL_MODEL_PATH else "legacy_plant"
load_model = Solar_Predictor.load_model(str(LOAD_MODEL_PATH)) if LOAD_MODEL_PATH.exists() else None


def merge_generation_weather(generation_df, weather_df):
    generation_df = generation_df.copy()
    weather_df = weather_df.copy()
    generation_df["DATE_TIME"] = Solar_Predictor.parse_datetime(generation_df["DATE_TIME"])
    weather_df["DATE_TIME"] = Solar_Predictor.parse_datetime(weather_df["DATE_TIME"])
    return pd.merge(generation_df, weather_df, on=["DATE_TIME", "PLANT_ID"], how="inner")


def load_visualization_data():
    if REGIONAL_DATA_PATH.exists():
        data = pd.read_csv(REGIONAL_DATA_PATH)
        data["DATE_TIME"] = Solar_Predictor.parse_datetime(data["DATE_TIME"])
        return data

    generation = pd.read_csv(BASE_DIR / "Plant_1_Generation_Data.csv")
    weather = pd.read_csv(BASE_DIR / "Plant_1_Weather_Sensor_Data.csv")
    return merge_generation_weather(generation, weather)


def load_regional_load_data():
    if not LOAD_DATA_PATH.exists():
        return pd.DataFrame()

    data = pd.read_csv(LOAD_DATA_PATH)
    data["DATE_TIME"] = Solar_Predictor.parse_datetime(data["DATE_TIME"])
    return data


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


def build_caiso_case_summary(case_id, case):
    metrics_data = read_json_file(case["metrics_path"])
    if metrics_data is None:
        return {
            "id": case_id,
            "title": case["title"],
            "title_zh": case["title_zh"],
            "available": False,
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
                "day_ahead_baseline": target_metric(metrics_data, "LOAD_MW", "day_ahead_baseline"),
            },
            "solar": {
                "label": "Solar generation",
                "label_zh": "太阳能发电",
                "model": target_metric(metrics_data, "SOLAR_MW"),
                "day_ahead_baseline": target_metric(metrics_data, "SOLAR_MW", "day_ahead_baseline"),
                "active_generation_model": target_metric(metrics_data, "SOLAR_MW", "active_generation_model"),
                "active_generation_day_ahead_baseline": target_metric(
                    metrics_data,
                    "SOLAR_MW",
                    "active_generation_day_ahead_baseline",
                ),
            },
            "wind": {
                "label": "Wind generation",
                "label_zh": "风电",
                "model": target_metric(metrics_data, "WIND_MW"),
                "day_ahead_baseline": target_metric(metrics_data, "WIND_MW", "day_ahead_baseline"),
            },
            "net_load": {
                "label": "Net load",
                "label_zh": "净负荷",
                "model": target_metric(metrics_data, "NET_LOAD_MW"),
            },
        },
    }


try:
    plant1_merged = load_visualization_data()
except Exception as exc:
    print(f"Warning: Could not load data for visualization: {exc}")
    plant1_merged = pd.DataFrame()

try:
    load_power_data = load_regional_load_data()
except Exception as exc:
    print(f"Warning: Could not load regional load data: {exc}")
    load_power_data = pd.DataFrame()


def plot_response():
    buffer = io.BytesIO()
    plt.tight_layout()
    plt.savefig(buffer, format="png")
    buffer.seek(0)
    plt.close()
    return Response(content=buffer.getvalue(), media_type="image/png")


def build_regional_input(payload):
    payload = payload_to_dict(payload)
    region_id = payload.get("region_id")
    if region_id not in REGION_BY_ID:
        raise ValueError("Unknown region_id")

    region = REGION_BY_ID[region_id]
    date_time = payload["DATE_TIME"]
    irradiation = float(payload["IRRADIATION"])
    ambient_temperature = float(payload["AMBIENT_TEMPERATURE"])
    wind_speed = float(payload.get("WIND_SPEED", 2.0))
    relative_humidity = float(payload.get("RELATIVE_HUMIDITY", 70.0))
    module_temperature = float(payload.get("MODULE_TEMPERATURE", ambient_temperature + 0.025 * irradiation))

    input_df = pd.DataFrame(
        [
            {
                "DATE_TIME": date_time,
                "REGION_CODE": SOUTHERN_GRID_REGIONS.index(region),
                "LATITUDE": region["latitude"],
                "LONGITUDE": region["longitude"],
                "CAPACITY_MW": region["capacity_mw"],
                "PEAK_LOAD_MW": region["peak_load_mw"],
                "STORAGE_POWER_MW": region["storage_power_mw"],
                "STORAGE_ENERGY_MWH": region["storage_energy_mwh"],
                "AMBIENT_TEMPERATURE": ambient_temperature,
                "RELATIVE_HUMIDITY": relative_humidity,
                "WIND_SPEED": wind_speed,
                "IRRADIATION": irradiation,
                "MODULE_TEMPERATURE": module_temperature,
            }
        ]
    )
    return region, input_df


def build_dispatch_assessment(solar_mw, load_mw, region):
    solar_share = solar_mw / load_mw if load_mw > 0 else 0.0
    net_load_mw = max(load_mw - solar_mw, 0.0)

    if solar_share >= 0.18:
        supply_level = "high"
    elif solar_share >= 0.08:
        supply_level = "medium"
    else:
        supply_level = "low"

    if solar_mw >= region["capacity_mw"] * 0.75:
        ramp_risk = "medium"
    elif solar_mw <= region["capacity_mw"] * 0.08:
        ramp_risk = "low-solar"
    else:
        ramp_risk = "low"

    if supply_level == "high":
        recommendation = "PV output is strong for this regional scenario. Prioritize local consumption and monitor midday downward net-load ramps."
    elif supply_level == "medium":
        recommendation = "PV output can offset part of regional demand. Keep conventional generation and load-side flexibility ready for evening ramp-up."
    else:
        recommendation = "PV contribution is limited. Dispatch planning should rely mainly on load forecast, reserve margin, and other flexible resources."

    return {
        "load_mw": load_mw,
        "net_load_mw": net_load_mw,
        "solar_share_percent": solar_share * 100.0,
        "supply_level": supply_level,
        "ramp_risk": ramp_risk,
        "recommendation": recommendation,
    }


def build_storage_dispatch(solar_mw, load_mw, region, date_time, storage_soc_percent=50.0):
    timestamp = pd.to_datetime(date_time)
    return optimize_storage_step(
        solar_mw=solar_mw,
        load_mw=load_mw,
        storage_power_mw=region["storage_power_mw"],
        storage_energy_mwh=region["storage_energy_mwh"],
        peak_load_mw=region["peak_load_mw"],
        hour=int(timestamp.hour),
        storage_soc_percent=storage_soc_percent,
    )


app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")


@app.get("/")
async def read_index():
    return FileResponse(str(BASE_DIR / "static" / "index.html"))


@app.get("/health")
async def health_check():
    return {
        "status": "ok",
        "mode": MODEL_MODE,
        "model_loaded": model.model is not None,
        "load_model_loaded": load_model is not None and load_model.model is not None,
        "feature_count": len(model.features or []),
        "load_feature_count": len(load_model.features or []) if load_model else 0,
        "visualization_rows": int(len(plant1_merged)),
        "load_visualization_rows": int(len(load_power_data)),
    }


@app.get("/regions")
async def get_regions():
    return {
        "regions": SOUTHERN_GRID_REGIONS,
    }


@app.get("/caiso/backtests")
async def get_caiso_backtests():
    return {
        "source": "CAISO OASIS public grid data",
        "source_zh": "CAISO OASIS 公开电网数据",
        "description": "Historical load, solar generation, wind generation, and day-ahead forecast fields are used for backtesting and rolling evaluation.",
        "description_zh": "使用历史负荷、太阳能发电、风电和日前预测字段，完成历史回测与滚动预测评估。",
        "cases": [build_caiso_case_summary(case_id, case) for case_id, case in CAISO_BACKTESTS.items()],
    }


@app.post("/predict")
async def predict(payload: LegacyPredictionRequest):
    try:
        payload_data = payload_to_dict(payload)
        input_df = pd.DataFrame(payload_data["data"])
        predictions = model.predict(input_df)
        return {
            "status": "success",
            "predictions": predictions.tolist(),
            "target": model.target,
            "mode": MODEL_MODE,
        }
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Prediction failed: {exc}") from exc


@app.get("/features")
async def get_features():
    return {
        "features": model.features,
        "target": model.target,
        "mode": MODEL_MODE,
    }


@app.post("/predict_region")
async def predict_region(payload: RegionalPredictionRequest):
    if MODEL_MODE != "regional_solar":
        raise HTTPException(status_code=400, detail="Regional solar model is not available. Run train_regional_model.py first.")

    try:
        region, input_df = build_regional_input(payload)
        prediction = float(model.predict(input_df)[0])
        return {
            "status": "success",
            "mode": MODEL_MODE,
            "region": region,
            "prediction_mw": prediction,
            "target": model.target,
        }
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Regional prediction failed: {exc}") from exc


@app.post("/predict_load")
async def predict_load(payload: RegionalPredictionRequest):
    if load_model is None:
        raise HTTPException(status_code=400, detail="Regional load model is not available. Run train_load_model.py first.")

    try:
        region, input_df = build_regional_input(payload)
        prediction = float(load_model.predict(input_df)[0])
        return {
            "status": "success",
            "mode": "regional_load",
            "region": region,
            "prediction_mw": prediction,
            "target": load_model.target,
        }
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Load prediction failed: {exc}") from exc


@app.post("/predict_dispatch")
async def predict_dispatch(payload: RegionalPredictionRequest):
    if MODEL_MODE != "regional_solar":
        raise HTTPException(status_code=400, detail="Regional solar model is not available. Run train_regional_model.py first.")
    if load_model is None:
        raise HTTPException(status_code=400, detail="Regional load model is not available. Run train_load_model.py first.")

    try:
        payload_data = payload_to_dict(payload)
        region, input_df = build_regional_input(payload)
        solar_mw = float(model.predict(input_df)[0])
        load_mw = float(load_model.predict(input_df)[0])
        assessment = build_dispatch_assessment(solar_mw, load_mw, region)
        storage = build_storage_dispatch(
            solar_mw,
            load_mw,
            region,
            payload_data["DATE_TIME"],
            payload_data.get("storage_soc_percent", 50.0),
        )
        return {
            "status": "success",
            "mode": "generation_load_dispatch",
            "region": region,
            "solar_prediction_mw": solar_mw,
            "load_prediction_mw": load_mw,
            "dispatch_assessment": assessment,
            "storage_dispatch": storage,
        }
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Dispatch prediction failed: {exc}") from exc


@app.post("/predict_storage_dispatch")
async def predict_storage_dispatch(payload: RegionalPredictionRequest):
    if MODEL_MODE != "regional_solar":
        raise HTTPException(status_code=400, detail="Regional solar model is not available. Run train_regional_model.py first.")
    if load_model is None:
        raise HTTPException(status_code=400, detail="Regional load model is not available. Run train_load_model.py first.")

    try:
        payload_data = payload_to_dict(payload)
        region, input_df = build_regional_input(payload)
        solar_mw = float(model.predict(input_df)[0])
        load_mw = float(load_model.predict(input_df)[0])
        storage = build_storage_dispatch(
            solar_mw,
            load_mw,
            region,
            payload_data["DATE_TIME"],
            payload_data.get("storage_soc_percent", 50.0),
        )
        return {
            "status": "success",
            "mode": "generation_load_storage_dispatch",
            "region": region,
            "solar_prediction_mw": solar_mw,
            "load_prediction_mw": load_mw,
            "storage_dispatch": storage,
        }
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Storage dispatch failed: {exc}") from exc


@app.get("/feature_importance")
async def get_feature_importance():
    try:
        importance_df = model.get_feature_importance()
        return {
            "status": "success",
            "importance": importance_df.to_dict(orient="records"),
        }
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Failed to get feature importance: {exc}") from exc


@app.get("/plot/timeseries")
async def get_timeseries_plot():
    if plant1_merged.empty:
        raise HTTPException(status_code=404, detail="Data not available for plotting")

    try:
        if MODEL_MODE == "regional_solar":
            df_plot = plant1_merged.copy()
            df_plot = df_plot[df_plot["REGION_ID"] == "guangdong_guangzhou"].sort_values("DATE_TIME")
            processed_eval = model.data_process(df_plot)
            predictions = model.model.predict(processed_eval[model.features])
            df_plot = pd.DataFrame(
                {
                    "Date": processed_eval["DATE_TIME"],
                    "Actual": processed_eval[model.target].values,
                    "Predicted": predictions,
                }
            ).sort_values("Date")
            df_plot.set_index("Date", inplace=True)

            plt.figure(figsize=(15, 8))
            sample = df_plot.tail(240)
            plt.plot(sample.index, sample["Actual"], label="Estimated regional PV output", color="#1f77b4", linewidth=2)
            plt.plot(sample.index, sample["Predicted"], label="Model prediction", color="#d62728", linewidth=2, linestyle="--")
            plt.title("Guangdong - Guangzhou Regional Solar Output Forecast", fontsize=16, fontweight="bold")
            plt.ylabel("Power (MW)")
            plt.xlabel("Time")
            plt.legend()
            plt.grid(True, alpha=0.3)
            plt.xticks(rotation=45)
            return plot_response()

        processed_eval = model.data_process(plant1_merged)
        x_eval = processed_eval[model.features]
        y_eval = processed_eval[model.target]
        predictions = model.model.predict(x_eval)

        df_plot = pd.DataFrame(
            {
                "Date": processed_eval["DATE_TIME"],
                "Actual_DAILY_YIELD": y_eval.values,
                "Predicted_DAILY_YIELD": predictions,
            }
        ).sort_values("Date")
        df_plot.set_index("Date", inplace=True)

        plt.figure(figsize=(15, 10))
        plt.subplot(2, 1, 1)
        plt.plot(
            df_plot.index,
            df_plot["Actual_DAILY_YIELD"],
            label="Actual Daily Yield",
            color="blue",
            linewidth=1.5,
            alpha=0.8,
        )
        plt.plot(
            df_plot.index,
            df_plot["Predicted_DAILY_YIELD"],
            label="Predicted Daily Yield",
            color="red",
            linewidth=1.5,
            alpha=0.7,
            linestyle="--",
        )
        plt.title("Plant 1 - Time series trend of solar power generation", fontsize=16, fontweight="bold")
        plt.ylabel("Daily Yield")
        plt.legend()
        plt.grid(True, alpha=0.3)
        plt.xticks(rotation=45)

        plt.subplot(2, 1, 2)
        last_days = df_plot.tail(200) if len(df_plot) > 72 else df_plot
        plt.plot(
            last_days.index,
            last_days["Actual_DAILY_YIELD"],
            label="Actual Daily Yield",
            color="blue",
            linewidth=2,
            alpha=0.9,
        )
        plt.plot(
            last_days.index,
            last_days["Predicted_DAILY_YIELD"],
            label="Predicted Daily Yield",
            color="red",
            linewidth=2,
            alpha=0.8,
            linestyle="--",
        )
        plt.title("Plant 1 - Recent Trend (Zoomed)", fontsize=14, fontweight="bold")
        plt.ylabel("Daily Yield")
        plt.xlabel("Time")
        plt.legend()
        plt.grid(True, alpha=0.3)
        plt.xticks(rotation=45)

        return plot_response()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Plot generation failed: {exc}") from exc


@app.get("/plot/heatmap")
async def get_heatmap_plot():
    if plant1_merged.empty:
        raise HTTPException(status_code=404, detail="Data not available for plotting")

    try:
        if MODEL_MODE == "regional_solar":
            df = plant1_merged[plant1_merged["REGION_ID"] == "guangdong_guangzhou"].copy()
            df["DATE_TIME"] = Solar_Predictor.parse_datetime(df["DATE_TIME"])
            df["Hour"] = df["DATE_TIME"].dt.hour
            df["Date"] = df["DATE_TIME"].dt.date
            pivot_table = df.pivot_table(values=model.target, index="Date", columns="Hour", aggfunc="mean")

            plt.figure(figsize=(15, 8))
            sns.heatmap(pivot_table, cmap="YlOrRd", cbar_kws={"label": "Solar output (MW)"}, xticklabels=2)
            plt.title("Guangdong - Guangzhou Regional Solar Output Heatmap", fontsize=16, fontweight="bold")
            plt.xlabel("Hour")
            plt.ylabel("Date")
            return plot_response()

        df = plant1_merged.copy()
        df["DATE_TIME"] = Solar_Predictor.parse_datetime(df["DATE_TIME"])
        df["Hour"] = df["DATE_TIME"].dt.hour
        df["Date"] = df["DATE_TIME"].dt.date

        pivot_table = df.pivot_table(
            values="DAILY_YIELD",
            index="Date",
            columns="Hour",
            aggfunc="mean",
        )

        plt.figure(figsize=(15, 8))
        sns.heatmap(pivot_table, cmap="YlOrRd", cbar_kws={"label": "Average yield"}, xticklabels=2)
        plt.title("Daily Yield Generation Heatmap", fontsize=16, fontweight="bold")
        plt.xlabel("Hour")
        plt.ylabel("Date")

        return plot_response()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Heatmap generation failed: {exc}") from exc


@app.get("/plot/load_balance")
async def get_load_balance_plot():
    if load_power_data.empty:
        raise HTTPException(status_code=404, detail="Regional load data not available. Run train_load_model.py first.")
    if MODEL_MODE != "regional_solar":
        raise HTTPException(status_code=400, detail="Regional solar model is not available.")

    try:
        df = load_power_data[load_power_data["REGION_ID"] == "guangdong_guangzhou"].copy()
        df = df.sort_values("DATE_TIME").tail(240)
        processed_solar = model.data_process(df)
        processed_load = load_model.data_process(df) if load_model else processed_solar

        solar_prediction = model.model.predict(processed_solar[model.features])
        if load_model:
            load_prediction = load_model.model.predict(processed_load[load_model.features])
        else:
            load_prediction = processed_load["REGIONAL_LOAD_MW"].values

        plot_df = pd.DataFrame(
            {
                "Date": processed_solar["DATE_TIME"],
                "Predicted PV Output": solar_prediction,
                "Predicted Load Demand": load_prediction,
            }
        ).sort_values("Date")
        plot_df["Net Load"] = plot_df["Predicted Load Demand"] - plot_df["Predicted PV Output"]

        plt.figure(figsize=(15, 8))
        plt.plot(plot_df["Date"], plot_df["Predicted Load Demand"], label="Predicted load demand", color="#334155", linewidth=2)
        plt.plot(plot_df["Date"], plot_df["Net Load"], label="Net load after PV", color="#f97316", linewidth=2)
        plt.plot(plot_df["Date"], plot_df["Predicted PV Output"], label="Predicted PV output", color="#16a34a", linewidth=2)
        plt.title("Guangdong - Guangzhou PV Output vs Load Demand", fontsize=16, fontweight="bold")
        plt.ylabel("Power (MW)")
        plt.xlabel("Time")
        plt.legend()
        plt.grid(True, alpha=0.3)
        plt.xticks(rotation=45)
        return plot_response()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Load balance plot generation failed: {exc}") from exc


@app.get("/plot/storage_strategy")
async def get_storage_strategy_plot():
    if load_power_data.empty:
        raise HTTPException(status_code=404, detail="Regional load data not available. Run train_load_model.py first.")
    if MODEL_MODE != "regional_solar" or load_model is None:
        raise HTTPException(status_code=400, detail="Regional solar and load models are required.")

    try:
        region = REGION_BY_ID["guangdong_guangzhou"]
        df = load_power_data[load_power_data["REGION_ID"] == region["region_id"]].copy()
        df = df.sort_values("DATE_TIME").tail(240)
        processed_solar = model.data_process(df)
        processed_load = load_model.data_process(df)

        solar_prediction = model.model.predict(processed_solar[model.features])
        load_prediction = load_model.model.predict(processed_load[load_model.features])

        strategy_rows = []
        soc = 50.0
        for date_time, solar_mw, load_mw in zip(processed_solar["DATE_TIME"], solar_prediction, load_prediction):
            storage = build_storage_dispatch(float(solar_mw), float(load_mw), region, date_time, soc)
            signed_storage_power = storage["storage_power_mw"]
            if storage["action"] == "charge":
                signed_storage_power = -signed_storage_power
            soc = storage["next_soc_percent"]
            strategy_rows.append(
                {
                    "Date": date_time,
                    "Predicted Load": float(load_mw),
                    "PV Output": float(solar_mw),
                    "Net Load After Storage": storage["net_load_after_storage_mw"],
                    "Storage Power": signed_storage_power,
                    "SOC": soc,
                }
            )

        plot_df = pd.DataFrame(strategy_rows).sort_values("Date")

        plt.figure(figsize=(15, 9))
        plt.subplot(2, 1, 1)
        plt.plot(plot_df["Date"], plot_df["Predicted Load"], label="Predicted load", color="#334155", linewidth=2)
        plt.plot(plot_df["Date"], plot_df["Net Load After Storage"], label="Net load after storage", color="#7c3aed", linewidth=2)
        plt.plot(plot_df["Date"], plot_df["PV Output"], label="PV output", color="#16a34a", linewidth=1.8)
        plt.title("Guangdong - Guangzhou Generation-Load-Storage Dispatch Strategy", fontsize=16, fontweight="bold")
        plt.ylabel("Power (MW)")
        plt.legend()
        plt.grid(True, alpha=0.3)
        plt.xticks(rotation=35)

        plt.subplot(2, 1, 2)
        plt.bar(plot_df["Date"], plot_df["Storage Power"], label="Storage power (+ discharge / - charge)", color="#0ea5e9", width=0.03)
        plt.plot(plot_df["Date"], plot_df["SOC"], label="Storage SOC (%)", color="#f97316", linewidth=2)
        plt.axhline(0, color="#64748b", linewidth=1)
        plt.ylabel("Storage MW / SOC %")
        plt.xlabel("Time")
        plt.legend()
        plt.grid(True, alpha=0.3)
        plt.xticks(rotation=35)
        return plot_response()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Storage strategy plot generation failed: {exc}") from exc


@app.get("/plot/caiso_backtest")
async def get_caiso_backtest_plot(period: str = "2025", target: str = "net_load"):
    case = CAISO_BACKTESTS.get(period)
    if case is None:
        raise HTTPException(status_code=404, detail="Unknown CAISO backtest period.")
    if not case["prediction_path"].exists():
        raise HTTPException(status_code=404, detail="CAISO prediction file is not available.")

    target_columns = {
        "load": ("LOAD_MW", "PREDICTED_LOAD_MW", "Load demand"),
        "solar": ("SOLAR_MW", "PREDICTED_SOLAR_MW", "Solar generation"),
        "wind": ("WIND_MW", "PREDICTED_WIND_MW", "Wind generation"),
        "net_load": ("NET_LOAD_MW", "PREDICTED_NET_LOAD_MW", "Net load"),
    }
    if target not in target_columns:
        raise HTTPException(status_code=404, detail="Unknown CAISO target.")

    actual_col, predicted_col, title = target_columns[target]
    try:
        df = pd.read_csv(case["prediction_path"])
        df["DATE_TIME_LOCAL"] = pd.to_datetime(df["DATE_TIME_LOCAL"], errors="coerce")
        df = df.dropna(subset=["DATE_TIME_LOCAL", actual_col, predicted_col]).sort_values("DATE_TIME_LOCAL")
        if df.empty:
            raise HTTPException(status_code=404, detail="No plottable CAISO rows.")

        plot_df = df.tail(336)
        plt.figure(figsize=(15, 8))
        plt.plot(plot_df["DATE_TIME_LOCAL"], plot_df[actual_col], label="Actual", color="#0f172a", linewidth=2)
        plt.plot(
            plot_df["DATE_TIME_LOCAL"],
            plot_df[predicted_col],
            label="Predicted",
            color="#2563eb",
            linewidth=2,
            linestyle="--",
        )
        plt.title(f"CAISO {period} {title}: Actual vs Predicted", fontsize=16, fontweight="bold")
        plt.ylabel("Power (MW)")
        plt.xlabel("Local time")
        plt.legend()
        plt.grid(True, alpha=0.3)
        plt.xticks(rotation=35)
        return plot_response()
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"CAISO plot generation failed: {exc}") from exc


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
