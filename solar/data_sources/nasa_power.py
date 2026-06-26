from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen
import argparse
import json
import sys

import pandas as pd

BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE_DIR))

from regions import SOUTHERN_GRID_REGIONS, region_code


DATA_DIR = BASE_DIR / "data"
NASA_POWER_URL = "https://power.larc.nasa.gov/api/temporal/hourly/point"

NASA_PARAMETERS = [
    "T2M",
    "RH2M",
    "WS2M",
    "ALLSKY_SFC_SW_DWN",
]


def estimate_module_temperature(ambient_temperature, irradiation):
    return ambient_temperature + 0.025 * irradiation


def estimate_solar_power_mw(irradiation, module_temperature, capacity_mw):
    normalized_irradiance = (irradiation / 1000.0).clip(lower=0.0, upper=1.2)
    temperature_factor = 1.0 - 0.004 * (module_temperature - 25.0)
    performance_ratio = 0.82
    power = capacity_mw * normalized_irradiance * temperature_factor * performance_ratio
    return power.clip(lower=0.0, upper=capacity_mw)


def build_nasa_url(region, start, end):
    query = {
        "parameters": ",".join(NASA_PARAMETERS),
        "community": "RE",
        "longitude": region["longitude"],
        "latitude": region["latitude"],
        "start": start,
        "end": end,
        "format": "JSON",
        "time-standard": "LST",
    }
    return f"{NASA_POWER_URL}?{urlencode(query)}"


def fetch_region(region, start, end, timeout=60):
    url = build_nasa_url(region, start, end)
    with urlopen(url, timeout=timeout) as response:
        payload = json.load(response)

    parameters = payload["properties"]["parameter"]
    frame = pd.DataFrame(parameters)
    frame.index = pd.to_datetime(frame.index, format="%Y%m%d%H")
    frame = frame.rename(
        columns={
            "T2M": "AMBIENT_TEMPERATURE",
            "RH2M": "RELATIVE_HUMIDITY",
            "WS2M": "WIND_SPEED",
            "ALLSKY_SFC_SW_DWN": "IRRADIATION",
        }
    )
    frame = frame.reset_index().rename(columns={"index": "DATE_TIME"})
    frame["REGION_ID"] = region["region_id"]
    frame["REGION_NAME"] = region["region_name"]
    frame["PROVINCE"] = region["province"]
    frame["REGION_CODE"] = region_code(region["region_id"])
    frame["LATITUDE"] = region["latitude"]
    frame["LONGITUDE"] = region["longitude"]
    frame["CAPACITY_MW"] = region["capacity_mw"]
    frame["MODULE_TEMPERATURE"] = estimate_module_temperature(
        frame["AMBIENT_TEMPERATURE"],
        frame["IRRADIATION"],
    )
    frame["SOLAR_POWER_MW"] = estimate_solar_power_mw(
        frame["IRRADIATION"],
        frame["MODULE_TEMPERATURE"],
        frame["CAPACITY_MW"],
    )
    return frame


def build_dataset(start, end, regions=None):
    selected_regions = regions or SOUTHERN_GRID_REGIONS
    frames = []
    for region in selected_regions:
        print(f"Fetching NASA POWER data for {region['region_name']}...")
        frames.append(fetch_region(region, start, end))
    dataset = pd.concat(frames, ignore_index=True)
    dataset = dataset.sort_values(["REGION_ID", "DATE_TIME"])
    return dataset


def main():
    parser = argparse.ArgumentParser(description="Fetch NASA POWER data for representative regional scenarios.")
    parser.add_argument("--start", default="20240101", help="Start date in YYYYMMDD format.")
    parser.add_argument("--end", default="20241231", help="End date in YYYYMMDD format.")
    parser.add_argument(
        "--output",
        default=str(DATA_DIR / "south_china_solar_power.csv"),
        help="Output CSV path.",
    )
    args = parser.parse_args()

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    dataset = build_dataset(args.start, args.end)
    dataset.to_csv(output, index=False)
    print(f"Saved {len(dataset):,} rows to {output}")


if __name__ == "__main__":
    main()
