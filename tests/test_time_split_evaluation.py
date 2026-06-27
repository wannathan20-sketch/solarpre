from pathlib import Path
import sys
import unittest

import pandas as pd


ROOT_DIR = Path(__file__).resolve().parents[1]
SOLAR_DIR = ROOT_DIR / "solar"
sys.path.insert(0, str(SOLAR_DIR))

from grid_backtest import build_predictions, metrics  # noqa: E402


class EiaTimeSplitBacktestTest(unittest.TestCase):
    def test_build_predictions_uses_past_rows_to_predict_future_window(self):
        train_hours = pd.date_range("2024-01-01 00:00:00", periods=48, freq="h")
        predict_hours = pd.date_range("2025-01-01 00:00:00", periods=6, freq="h")
        timestamps = [*train_hours, *predict_hours]
        frame = pd.DataFrame({"DATE_TIME_LOCAL": timestamps})
        frame["LOAD_MW"] = 100.0 + frame.index.to_series().astype(float)
        frame["LOAD_FORECAST_MW"] = frame["LOAD_MW"] + 1.0
        frame["SOLAR_MW"] = (frame.index.to_series() % 8).astype(float)
        frame["WIND_MW"] = 10.0 + (frame.index.to_series() % 5).astype(float)

        predictions, report = build_predictions(
            frame,
            pd.Timestamp("2024-01-01 00:00:00"),
            pd.Timestamp("2024-12-31 23:59:59"),
            pd.Timestamp("2025-01-01 00:00:00"),
            pd.Timestamp("2025-12-31 23:59:59"),
        )

        self.assertEqual(len(predictions), 6)
        self.assertEqual(report["targets"]["LOAD_MW"]["train_rows"], 48)
        self.assertIn("PREDICTED_NET_LOAD_MW", predictions.columns)

    def test_metrics_reports_mae_rmse_and_mape(self):
        result = metrics([100.0, 200.0], [90.0, 220.0])

        self.assertAlmostEqual(result["mae"], 15.0)
        self.assertAlmostEqual(result["rmse"], 15.811388300841896)
        self.assertAlmostEqual(result["mape_percent"], 10.0)


if __name__ == "__main__":
    unittest.main()
