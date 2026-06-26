import asyncio
from pathlib import Path
import sys
import unittest

from pydantic import ValidationError


ROOT_DIR = Path(__file__).resolve().parents[1]
SOLAR_DIR = ROOT_DIR / "solar"
sys.path.insert(0, str(SOLAR_DIR))

import app  # noqa: E402
from schemas import RegionalPredictionRequest  # noqa: E402


VALID_PAYLOAD = {
    "region_id": "guangdong_guangzhou",
    "DATE_TIME": "2024-07-01 12:00:00",
    "AMBIENT_TEMPERATURE": 32.0,
    "RELATIVE_HUMIDITY": 72.0,
    "WIND_SPEED": 2.6,
    "IRRADIATION": 760.0,
    "storage_soc_percent": 50.0,
}


class RegionalPredictionContractTest(unittest.TestCase):
    def test_regional_request_accepts_valid_payload(self):
        request = RegionalPredictionRequest.model_validate(VALID_PAYLOAD)

        self.assertEqual(request.region_id, "guangdong_guangzhou")
        self.assertEqual(request.storage_soc_percent, 50.0)

    def test_regional_request_rejects_invalid_soc(self):
        payload = {**VALID_PAYLOAD, "storage_soc_percent": 120.0}

        with self.assertRaises(ValidationError):
            RegionalPredictionRequest.model_validate(payload)

    def test_regional_request_rejects_negative_irradiation(self):
        payload = {**VALID_PAYLOAD, "IRRADIATION": -1.0}

        with self.assertRaises(ValidationError):
            RegionalPredictionRequest.model_validate(payload)

    def test_dispatch_endpoint_accepts_schema_instance(self):
        request = RegionalPredictionRequest.model_validate(VALID_PAYLOAD)

        result = asyncio.run(app.predict_dispatch(request))

        self.assertEqual(result["status"], "success")
        self.assertIn("dispatch_assessment", result)
        self.assertIn("storage_dispatch", result)


if __name__ == "__main__":
    unittest.main()
