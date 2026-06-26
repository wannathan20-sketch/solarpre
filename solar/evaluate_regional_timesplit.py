from pathlib import Path
import argparse
import json

import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error
import xgboost as xgb

from solar_predictor import Solar_Predictor
from train_load_model import REGIONAL_LOAD_FEATURES
from train_regional_model import REGIONAL_SOLAR_FEATURES


BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DEFAULT_TRAIN_END = "2024-09-30"


def normalize_train_end(value):
    timestamp = pd.Timestamp(value)
    if len(str(value)) == 10:
        timestamp = timestamp + pd.Timedelta(hours=23, minutes=59, seconds=59)
    return timestamp


def split_by_time(frame, train_end):
    data = frame.copy()
    data["DATE_TIME"] = Solar_Predictor.parse_datetime(data["DATE_TIME"])
    data = data.dropna(subset=["DATE_TIME"]).sort_values("DATE_TIME")
    cutoff = normalize_train_end(train_end)
    train = data[data["DATE_TIME"] <= cutoff].copy()
    test = data[data["DATE_TIME"] > cutoff].copy()
    return train, test


def mape(y_true, y_pred):
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)
    mask = np.abs(y_true) > 1e-6
    if not mask.any():
        return None
    return float(np.mean(np.abs((y_true[mask] - y_pred[mask]) / y_true[mask])) * 100.0)


def regression_metrics(y_true, y_pred):
    values = pd.DataFrame({"y_true": y_true, "y_pred": y_pred}).dropna()
    if values.empty:
        return {
            "rows": 0,
            "mae": None,
            "rmse": None,
            "mape_percent": None,
        }
    return {
        "rows": int(len(values)),
        "mae": float(mean_absolute_error(values["y_true"], values["y_pred"])),
        "rmse": float(np.sqrt(mean_squared_error(values["y_true"], values["y_pred"]))),
        "mape_percent": mape(values["y_true"], values["y_pred"]),
    }


def evaluate_time_split(data, target, features, train_end=DEFAULT_TRAIN_END, xgb_params=None):
    predictor = Solar_Predictor(target)
    processed = predictor.data_process(data)
    train, test = split_by_time(processed, train_end)

    required_columns = [*features, target]
    train = train.dropna(subset=required_columns)
    test = test.dropna(subset=required_columns)
    if train.empty:
        raise ValueError("Training split has no usable rows.")
    if test.empty:
        raise ValueError("Test split has no usable future rows.")

    params = {
        "n_estimators": 180,
        "learning_rate": 0.05,
        "max_depth": 6,
        "subsample": 0.9,
        "colsample_bytree": 0.9,
        "random_state": 42,
    }
    if xgb_params:
        params.update(xgb_params)

    model = xgb.XGBRegressor(**params)
    model.fit(train[features], train[target])
    predictions = model.predict(test[features])

    return {
        "target": target,
        "train_end": str(normalize_train_end(train_end)),
        "train_rows": int(len(train)),
        "test_rows": int(len(test)),
        "test_start": str(test["DATE_TIME"].min()),
        "test_end": str(test["DATE_TIME"].max()),
        "features": features,
        "model": regression_metrics(test[target].values, predictions),
    }


def load_dataset(kind):
    if kind == "solar":
        return pd.read_csv(DATA_DIR / "south_china_solar_power.csv")
    if kind == "load":
        return pd.read_csv(DATA_DIR / "south_china_load_power.csv")
    raise ValueError(f"Unsupported dataset kind: {kind}")


def evaluate_kind(kind, train_end):
    if kind == "solar":
        return evaluate_time_split(
            load_dataset("solar"),
            "SOLAR_POWER_MW",
            REGIONAL_SOLAR_FEATURES,
            train_end=train_end,
        )
    if kind == "load":
        return evaluate_time_split(
            load_dataset("load"),
            "REGIONAL_LOAD_MW",
            REGIONAL_LOAD_FEATURES,
            train_end=train_end,
        )
    raise ValueError(f"Unsupported dataset kind: {kind}")


def main():
    parser = argparse.ArgumentParser(description="Evaluate regional models with chronological train/test split.")
    parser.add_argument("--kind", choices=["solar", "load", "both"], default="both")
    parser.add_argument("--train-end", default=DEFAULT_TRAIN_END)
    parser.add_argument(
        "--output",
        default=str(DATA_DIR / "regional_timesplit_metrics.json"),
        help="Output JSON report path.",
    )
    args = parser.parse_args()

    kinds = ["solar", "load"] if args.kind == "both" else [args.kind]
    report = {
        "method": "chronological_time_split",
        "description": "Models train only on rows at or before train_end and evaluate on future rows.",
        "train_end": str(normalize_train_end(args.train_end)),
        "results": {kind: evaluate_kind(kind, args.train_end) for kind in kinds},
    }

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
