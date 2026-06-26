from pathlib import Path
import sys

import numpy as np
import pandas as pd

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

from regions import REGION_BY_ID
from solar_predictor import Solar_Predictor


SOLAR_DATA_PATH = BASE_DIR / "data" / "south_china_solar_power.csv"
LOAD_DATA_PATH = BASE_DIR / "data" / "south_china_load_power.csv"
MODEL_PATH = BASE_DIR / "south_china_load_model.joblib"

REGIONAL_LOAD_FEATURES = [
    "HOUR",
    "MONTH",
    "IF_DAYTIME",
    "DAY_OF_WEEK",
    "IS_WEEKEND",
    "SEASON",
    "REGION_CODE",
    "LATITUDE",
    "LONGITUDE",
    "PEAK_LOAD_MW",
    "AMBIENT_TEMPERATURE",
    "RELATIVE_HUMIDITY",
    "WIND_SPEED",
    "IRRADIATION",
    "TEMPERATURE_IRRADIATION",
]


def estimate_regional_load_mw(frame):
    data = frame.copy()
    data["DATE_TIME"] = Solar_Predictor.parse_datetime(data["DATE_TIME"])
    hour = data["DATE_TIME"].dt.hour
    month = data["DATE_TIME"].dt.month
    day_of_week = data["DATE_TIME"].dt.dayofweek

    morning_peak = np.exp(-((hour - 9) ** 2) / 18.0)
    evening_peak = np.exp(-((hour - 20) ** 2) / 10.0)
    midday_industry = np.exp(-((hour - 14) ** 2) / 32.0)
    daily_shape = 0.50 + 0.10 * morning_peak + 0.18 * evening_peak + 0.12 * midday_industry

    weekday_boost = np.where(day_of_week < 5, 0.07, -0.03)
    summer_boost = np.where(month.isin([6, 7, 8, 9]), 0.08, 0.0)
    winter_boost = np.where(month.isin([12, 1, 2]), 0.04, 0.0)

    cooling_load = np.maximum(data["AMBIENT_TEMPERATURE"] - 26.0, 0) * 0.020
    heating_load = np.maximum(16.0 - data["AMBIENT_TEMPERATURE"], 0) * 0.012
    humidity_stress = np.maximum(data["RELATIVE_HUMIDITY"] - 70.0, 0) * 0.0015
    wind_relief = np.minimum(data["WIND_SPEED"], 6.0) * 0.004

    normalized_load = (
        daily_shape
        + weekday_boost
        + summer_boost
        + winter_boost
        + cooling_load
        + heating_load
        + humidity_stress
        - wind_relief
    )
    normalized_load = np.clip(normalized_load, 0.34, 0.98)
    return data["PEAK_LOAD_MW"] * normalized_load


def build_load_dataset():
    if not SOLAR_DATA_PATH.exists():
        raise FileNotFoundError(
            f"Dataset not found: {SOLAR_DATA_PATH}. Run data_sources/nasa_power.py first."
        )

    dataset = pd.read_csv(SOLAR_DATA_PATH)
    dataset["PEAK_LOAD_MW"] = dataset["REGION_ID"].map(
        lambda region_id: REGION_BY_ID[region_id]["peak_load_mw"]
    )
    dataset["REGIONAL_LOAD_MW"] = estimate_regional_load_mw(dataset)
    return dataset


def main():
    print(f"Building regional load dataset from {SOLAR_DATA_PATH}...")
    dataset = build_load_dataset()
    LOAD_DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    dataset.to_csv(LOAD_DATA_PATH, index=False)
    print(f"Saved {len(dataset):,} rows to {LOAD_DATA_PATH}")

    model = Solar_Predictor("REGIONAL_LOAD_MW")
    model.set_features(REGIONAL_LOAD_FEATURES)
    model.cross_validate_train_XG(
        dataset,
        n_estimators=220,
        learning_rate=0.05,
        max_depth=6,
        subsample=0.9,
        colsample_bytree=0.9,
    )
    model.save_model(MODEL_PATH)

    print(f"Cross-validation R2: {model.cv_mean:.4f} +/- {model.cv_std:.4f}")
    print(f"Saved model to {MODEL_PATH}")


if __name__ == "__main__":
    main()
