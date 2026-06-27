from pathlib import Path
import sys
import unittest


ROOT_DIR = Path(__file__).resolve().parents[1]
SOLAR_DIR = ROOT_DIR / "solar"
sys.path.insert(0, str(SOLAR_DIR))

from storage_dispatch import optimize_storage_step  # noqa: E402


class StorageDispatchOptimizationTest(unittest.TestCase):
    def test_discharge_reduces_peak_load_without_crossing_reserve_soc(self):
        result = optimize_storage_step(
            solar_mw=100.0,
            load_mw=900.0,
            storage_power_mw=120.0,
            storage_energy_mwh=400.0,
            peak_load_mw=1000.0,
            hour=20,
            storage_soc_percent=20.0,
        )

        self.assertEqual(result["action"], "discharge")
        self.assertGreater(result["storage_power_mw"], 0.0)
        self.assertLess(result["net_load_after_storage_mw"], result["net_load_before_mw"])
        self.assertGreaterEqual(result["next_soc_percent"], result["reserve_soc_percent"])

    def test_charge_absorbs_surplus_without_crossing_max_soc(self):
        result = optimize_storage_step(
            solar_mw=600.0,
            load_mw=400.0,
            storage_power_mw=150.0,
            storage_energy_mwh=300.0,
            peak_load_mw=1000.0,
            hour=12,
            storage_soc_percent=94.0,
        )

        self.assertEqual(result["action"], "charge")
        self.assertGreater(result["storage_power_mw"], 0.0)
        self.assertLessEqual(result["next_soc_percent"], result["max_soc_percent"])

    def test_standby_when_no_charge_or_discharge_signal(self):
        result = optimize_storage_step(
            solar_mw=50.0,
            load_mw=500.0,
            storage_power_mw=120.0,
            storage_energy_mwh=400.0,
            peak_load_mw=1000.0,
            hour=3,
            storage_soc_percent=50.0,
        )

        self.assertEqual(result["action"], "standby")
        self.assertEqual(result["storage_power_mw"], 0.0)
        self.assertEqual(result["optimization_method"], "constrained_greedy_peak_shaving")


if __name__ == "__main__":
    unittest.main()
