from pathlib import Path
import argparse
import json

import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error
import xgboost as xgb


BASE_DIR = Path(__file__).resolve().parent

TARGETS = ["LOAD_MW", "SOLAR_MW", "WIND_MW"]
FORECAST_FEATURES = ["LOAD_FORECAST_MW", "SOLAR_FORECAST_MW", "WIND_FORECAST_MW"]
CALENDAR_FEATURES = ["HOUR", "MONTH", "DAY_OF_WEEK", "IS_WEEKEND", "SEASON"]


def parse_date(value):
    return pd.Timestamp(value).tz_localize(None)


def add_features(data):
    frame = data.copy()
    frame["DATE_TIME_LOCAL"] = pd.to_datetime(frame["DATE_TIME_LOCAL"], errors="coerce")
    frame = frame.dropna(subset=["DATE_TIME_LOCAL"])
    frame["HOUR"] = frame["DATE_TIME_LOCAL"].dt.hour
    frame["MONTH"] = frame["DATE_TIME_LOCAL"].dt.month
    frame["DAY_OF_WEEK"] = frame["DATE_TIME_LOCAL"].dt.dayofweek
    frame["IS_WEEKEND"] = (frame["DAY_OF_WEEK"] >= 5).astype(int)
    frame["SEASON"] = frame["MONTH"].map(
        lambda month: 0 if month in [3, 4, 5] else 1 if month in [6, 7, 8] else 2 if month in [9, 10, 11] else 3
    )
    for column in FORECAST_FEATURES:
        if column not in frame.columns:
            frame[column] = np.nan
    return frame.sort_values("DATE_TIME_LOCAL")


def feature_columns(data):
    available_forecasts = [column for column in FORECAST_FEATURES if data[column].notna().any()]
    return CALENDAR_FEATURES + available_forecasts


def clean_model_frame(data, features, target):
    columns = ["DATE_TIME_LOCAL", *features, target]
    frame = data[columns].copy()
    frame = frame.dropna(subset=features)
    frame = frame.dropna(subset=[target])
    return frame


def clean_prediction_frame(data, features):
    columns = ["DATE_TIME_LOCAL", *features, *[target for target in TARGETS if target in data.columns]]
    frame = data[columns].copy()
    frame = frame.dropna(subset=features)
    return frame


def mape(y_true, y_pred):
    y_true = np.asarray(y_true)
    y_pred = np.asarray(y_pred)
    mask = np.abs(y_true) > 1e-6
    if not mask.any():
        return None
    return float(np.mean(np.abs((y_true[mask] - y_pred[mask]) / y_true[mask])) * 100.0)


def metrics(y_true, y_pred):
    values = pd.DataFrame({"y_true": y_true, "y_pred": y_pred}).dropna()
    if values.empty:
        return None
    return {
        "mae": float(mean_absolute_error(values["y_true"], values["y_pred"])),
        "rmse": float(np.sqrt(mean_squared_error(values["y_true"], values["y_pred"]))),
        "mape_percent": mape(values["y_true"], values["y_pred"]),
    }


def metrics_for_active_generation(y_true, y_pred, minimum_mw=100.0):
    values = pd.DataFrame({"y_true": y_true, "y_pred": y_pred}).dropna()
    values = values[values["y_true"] > minimum_mw]
    if values.empty:
        return None

    result = metrics(values["y_true"], values["y_pred"])
    result["minimum_actual_mw"] = minimum_mw
    result["rows"] = int(len(values))
    return result


def train_one_model(train_data, features, target):
    frame = clean_model_frame(train_data, features, target)
    if len(frame) < 24:
        raise ValueError(f"Not enough training rows for {target}: {len(frame)}")

    model = xgb.XGBRegressor(
        n_estimators=260,
        learning_rate=0.05,
        max_depth=6,
        subsample=0.9,
        colsample_bytree=0.9,
        random_state=42,
    )
    model.fit(frame[features], frame[target])
    return model, len(frame)


def build_predictions(data, train_start, train_end, predict_start, predict_end):
    prepared = add_features(data)
    features = feature_columns(prepared)

    train_mask = (prepared["DATE_TIME_LOCAL"] >= train_start) & (prepared["DATE_TIME_LOCAL"] <= train_end)
    predict_mask = (prepared["DATE_TIME_LOCAL"] >= predict_start) & (prepared["DATE_TIME_LOCAL"] <= predict_end)
    train_data = prepared[train_mask].copy()
    predict_data = prepared[predict_mask].copy()

    if train_data.empty:
        raise ValueError("Training window has no rows.")
    if predict_data.empty:
        raise ValueError("Prediction window has no rows.")

    prediction_frame = clean_prediction_frame(predict_data, features).reset_index(drop=True)
    if prediction_frame.empty:
        raise ValueError("Prediction window has no rows with all required features.")

    output = prediction_frame[["DATE_TIME_LOCAL"]].copy()
    report = {
        "features": features,
        "train_start": str(train_start),
        "train_end": str(train_end),
        "predict_start": str(predict_start),
        "predict_end": str(predict_end),
        "targets": {},
    }

    for target in TARGETS:
        if target not in prepared.columns:
            continue

        model, train_rows = train_one_model(train_data, features, target)
        pred_col = f"PREDICTED_{target}"
        output[pred_col] = model.predict(prediction_frame[features])

        if target in prediction_frame.columns:
            output[target] = prediction_frame[target].values
            actual_rows = prediction_frame.dropna(subset=[target])
            if not actual_rows.empty:
                report["targets"][target] = {
                    "train_rows": int(train_rows),
                    "actual_rows": int(len(actual_rows)),
                    "model": metrics(actual_rows[target].values, output.loc[actual_rows.index, pred_col].values),
                }
                if target == "SOLAR_MW":
                    report["targets"][target]["active_generation_model"] = metrics_for_active_generation(
                        actual_rows[target].values,
                        output.loc[actual_rows.index, pred_col].values,
                    )

                forecast_col = target.replace("_MW", "_FORECAST_MW")
                if forecast_col in actual_rows.columns and actual_rows[forecast_col].notna().any():
                    report["targets"][target]["day_ahead_baseline"] = metrics(
                        actual_rows[target].values,
                        actual_rows[forecast_col].values,
                    )
                    if target == "SOLAR_MW":
                        report["targets"][target]["active_generation_day_ahead_baseline"] = metrics_for_active_generation(
                            actual_rows[target].values,
                            actual_rows[forecast_col].values,
                        )
        else:
            report["targets"][target] = {
                "train_rows": int(train_rows),
                "actual_rows": 0,
                "model": None,
            }

    if {"PREDICTED_LOAD_MW", "PREDICTED_SOLAR_MW", "PREDICTED_WIND_MW"}.issubset(output.columns):
        output["PREDICTED_NET_LOAD_MW"] = (
            output["PREDICTED_LOAD_MW"] - output["PREDICTED_SOLAR_MW"] - output["PREDICTED_WIND_MW"]
        )
    if {"LOAD_MW", "SOLAR_MW", "WIND_MW"}.issubset(output.columns):
        output["NET_LOAD_MW"] = output["LOAD_MW"] - output["SOLAR_MW"] - output["WIND_MW"]
        net_load_metric_rows = output[["NET_LOAD_MW", "PREDICTED_NET_LOAD_MW"]].dropna()
        report["targets"]["NET_LOAD_MW"] = {
            "actual_rows": int(len(net_load_metric_rows)),
            "model": metrics(net_load_metric_rows["NET_LOAD_MW"], net_load_metric_rows["PREDICTED_NET_LOAD_MW"])
            if "PREDICTED_NET_LOAD_MW" in output.columns and not net_load_metric_rows.empty
            else None,
        }

    return output, report


def main():
    parser = argparse.ArgumentParser(description="Backtest real grid load and renewable generation forecasts.")
    parser.add_argument("--input", required=True, help="Hourly real-grid CSV generated by a data source script.")
    parser.add_argument("--train-start", required=True, help="Training start date, YYYY-MM-DD.")
    parser.add_argument("--train-end", required=True, help="Training end date, YYYY-MM-DD.")
    parser.add_argument("--predict-start", required=True, help="Prediction window start date, YYYY-MM-DD.")
    parser.add_argument("--predict-end", required=True, help="Prediction window end date, YYYY-MM-DD.")
    parser.add_argument("--output", default=str(BASE_DIR / "data" / "grid_predictions.csv"))
    parser.add_argument("--metrics-output", default=str(BASE_DIR / "data" / "grid_backtest_metrics.json"))
    args = parser.parse_args()

    data = pd.read_csv(args.input)
    train_start = parse_date(args.train_start)
    train_end = parse_date(args.train_end) + pd.Timedelta(hours=23, minutes=59, seconds=59)
    predict_start = parse_date(args.predict_start)
    predict_end = parse_date(args.predict_end) + pd.Timedelta(hours=23, minutes=59, seconds=59)

    predictions, report = build_predictions(data, train_start, train_end, predict_start, predict_end)

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    predictions.to_csv(output, index=False)

    metrics_output = Path(args.metrics_output)
    metrics_output.parent.mkdir(parents=True, exist_ok=True)
    metrics_output.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print(f"Saved predictions to {output}")
    print(f"Saved metrics to {metrics_output}")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
