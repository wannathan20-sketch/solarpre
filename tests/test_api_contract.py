import asyncio
from pathlib import Path
import sys
import unittest


ROOT_DIR = Path(__file__).resolve().parents[1]
SOLAR_DIR = ROOT_DIR / "solar"
sys.path.insert(0, str(SOLAR_DIR))

import app  # noqa: E402


class EiaApiContractTest(unittest.TestCase):
    def test_eia_backtests_endpoint_returns_real_data_source(self):
        result = asyncio.run(app.get_eia_backtests())

        self.assertEqual(result["source"], "EIA Open Data electricity API")
        self.assertIn("2025", [case["id"] for case in result["cases"]])
        self.assertIn("2026", [case["id"] for case in result["cases"]])

    def test_health_reports_eia_only_mode(self):
        result = asyncio.run(app.health_check())

        self.assertEqual(result["mode"], "eia_real_grid_backtest")
        self.assertTrue(result["real_data_only"])


if __name__ == "__main__":
    unittest.main()
