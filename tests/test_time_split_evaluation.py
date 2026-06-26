from pathlib import Path
import sys
import unittest

import pandas as pd


ROOT_DIR = Path(__file__).resolve().parents[1]
SOLAR_DIR = ROOT_DIR / "solar"
sys.path.insert(0, str(SOLAR_DIR))

from evaluate_regional_timesplit import regression_metrics, split_by_time  # noqa: E402


class TimeSplitEvaluationTest(unittest.TestCase):
    def test_split_by_time_uses_future_rows_as_test_set(self):
        frame = pd.DataFrame(
            {
                "DATE_TIME": [
                    "2024-01-01 00:00:00",
                    "2024-09-30 23:00:00",
                    "2024-10-01 00:00:00",
                ],
                "target": [1.0, 2.0, 3.0],
            }
        )

        train, test = split_by_time(frame, "2024-09-30")

        self.assertEqual(len(train), 2)
        self.assertEqual(len(test), 1)
        self.assertLess(train["DATE_TIME"].max(), test["DATE_TIME"].min())

    def test_regression_metrics_reports_mae_rmse_and_mape(self):
        metrics = regression_metrics([100.0, 200.0], [90.0, 220.0])

        self.assertEqual(metrics["rows"], 2)
        self.assertAlmostEqual(metrics["mae"], 15.0)
        self.assertAlmostEqual(metrics["rmse"], 15.811388300841896)
        self.assertAlmostEqual(metrics["mape_percent"], 10.0)


if __name__ == "__main__":
    unittest.main()
