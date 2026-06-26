from pathlib import Path
import sys

import pandas as pd

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

from solar_predictor import Solar_Predictor


DATA_PATH = BASE_DIR / "data" / "south_china_solar_power.csv"
MODEL_PATH = BASE_DIR / "south_china_solar_model.joblib"

REGIONAL_SOLAR_FEATURES = [
    "HOUR",
    "MONTH",
    "IF_DAYTIME",
    "DAY_OF_WEEK",
    "IS_WEEKEND",
    "SEASON",
    "REGION_CODE",
    "LATITUDE",
    "LONGITUDE",
    "CAPACITY_MW",
    "AMBIENT_TEMPERATURE",
    "RELATIVE_HUMIDITY",
    "WIND_SPEED",
    "IRRADIATION",
    "MODULE_TEMPERATURE",
    "MODULE_AMBIENT_DIFF",
    "TEMPERATURE_IRRADIATION",
    "IRRADIATION_CAPACITY",
    "WIND_IRRADIATION",
]


def main():
    if not DATA_PATH.exists():
        raise FileNotFoundError(
            f"Dataset not found: {DATA_PATH}. Run data_sources/nasa_power.py first."
        )

    print(f"Loading regional dataset from {DATA_PATH}...")
    dataset = pd.read_csv(DATA_PATH)

    model = Solar_Predictor("SOLAR_POWER_MW")
    model.set_features(REGIONAL_SOLAR_FEATURES)
    model.cross_validate_train_XG(
        dataset,
        n_estimators=250,
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
