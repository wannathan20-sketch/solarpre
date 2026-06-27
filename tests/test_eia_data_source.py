from pathlib import Path
import sys
import unittest
from urllib.parse import parse_qs, urlparse

import pandas as pd


ROOT_DIR = Path(__file__).resolve().parents[1]
SOLAR_DIR = ROOT_DIR / "solar"
sys.path.insert(0, str(SOLAR_DIR))

from data_sources.eia_open_data import build_eia_url, normalize_region_data, normalize_fuel_type_data  # noqa: E402


class EiaDataSourceTest(unittest.TestCase):
    def test_build_eia_url_preserves_multiple_facet_values(self):
        url = build_eia_url(
            "region-data",
            api_key="test-key",
            respondent="CISO",
            start="2021-01-01T00",
            end="2021-01-01T05",
            extra_facets={"type": ["D", "DF"]},
        )

        query = parse_qs(urlparse(url).query)

        self.assertEqual(query["facets[type][]"], ["D", "DF"])

    def test_region_data_normalizes_load_and_forecast_rows(self):
        raw = pd.DataFrame(
            [
                {
                    "period": "2025-01-01T00",
                    "type": "D",
                    "respondent": "CISO",
                    "respondent-name": "California Independent System Operator",
                    "value": "21000",
                },
                {
                    "period": "2025-01-01T00",
                    "type": "DF",
                    "respondent": "CISO",
                    "respondent-name": "California Independent System Operator",
                    "value": "21250",
                },
            ]
        )

        normalized = normalize_region_data(raw)

        self.assertEqual(len(normalized), 1)
        self.assertEqual(float(normalized.loc[0, "LOAD_MW"]), 21000.0)
        self.assertEqual(float(normalized.loc[0, "LOAD_FORECAST_MW"]), 21250.0)

    def test_fuel_type_data_pivots_solar_and_wind_generation(self):
        raw = pd.DataFrame(
            [
                {"period": "2025-01-01T00", "respondent": "CISO", "fueltype": "SUN", "value": "1200"},
                {"period": "2025-01-01T00", "respondent": "CISO", "fueltype": "WND", "value": "800"},
            ]
        )

        normalized = normalize_fuel_type_data(raw)

        self.assertEqual(len(normalized), 1)
        self.assertEqual(float(normalized.loc[0, "SOLAR_MW"]), 1200.0)
        self.assertEqual(float(normalized.loc[0, "WIND_MW"]), 800.0)
        self.assertEqual(float(normalized.loc[0, "GENERATION_MW"]), 2000.0)


if __name__ == "__main__":
    unittest.main()
