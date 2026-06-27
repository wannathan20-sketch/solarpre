from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen
import argparse
import json
import os

import pandas as pd


BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BASE_DIR / "data"
EIA_API_BASE = "https://api.eia.gov/v2/electricity/rto"
DEFAULT_RESPONDENT = "CISO"
PAGE_SIZE = 5000

REGION_TYPE_MAP = {
    "D": "LOAD_MW",
    "DF": "LOAD_FORECAST_MW",
}

FUEL_TYPE_MAP = {
    "SUN": "SOLAR_MW",
    "WND": "WIND_MW",
}


def require_api_key(api_key=None):
    key = api_key or os.environ.get("EIA_API_KEY")
    if not key:
        raise RuntimeError(
            "EIA_API_KEY is required. Create a free key at https://www.eia.gov/opendata/ "
            "and export it before downloading EIA data."
        )
    return key


def eia_request(endpoint, api_key, respondent, start, end, extra_facets=None, offset=0, length=PAGE_SIZE):
    query = {
        "api_key": api_key,
        "frequency": "hourly",
        "data[0]": "value",
        "facets[respondent][]": respondent,
        "start": start,
        "end": end,
        "sort[0][column]": "period",
        "sort[0][direction]": "asc",
        "offset": str(offset),
        "length": str(length),
    }
    for facet_name, values in (extra_facets or {}).items():
        for value in values:
            query[f"facets[{facet_name}][]"] = value

    url = f"{EIA_API_BASE}/{endpoint}/data/?{urlencode(query, doseq=True)}"
    request = Request(url, headers={"User-Agent": "solar-pred-eia-client/1.0"})
    with urlopen(request, timeout=60) as response:
        return json.load(response)


def fetch_eia_frame(endpoint, api_key, respondent, start, end, extra_facets=None):
    rows = []
    offset = 0
    total = None
    while total is None or offset < total:
        payload = eia_request(
            endpoint,
            api_key=api_key,
            respondent=respondent,
            start=start,
            end=end,
            extra_facets=extra_facets,
            offset=offset,
        )
        response = payload.get("response", {})
        total = int(response.get("total", 0))
        batch = response.get("data", [])
        if not batch:
            break
        rows.extend(batch)
        offset += len(batch)
    return pd.DataFrame(rows)


def normalize_region_data(raw):
    if raw.empty:
        return pd.DataFrame(columns=["DATE_TIME_LOCAL", "REGION_ID", "REGION_NAME", "LOAD_MW", "LOAD_FORECAST_MW"])

    data = raw.copy()
    data["DATE_TIME_LOCAL"] = pd.to_datetime(data["period"], errors="coerce")
    data["value"] = pd.to_numeric(data["value"], errors="coerce")
    data["type"] = data["type"].astype(str)
    data = data[data["type"].isin(REGION_TYPE_MAP)]

    pivot = data.pivot_table(
        values="value",
        index=["DATE_TIME_LOCAL", "respondent"],
        columns="type",
        aggfunc="mean",
    ).reset_index()
    pivot = pivot.rename(columns=REGION_TYPE_MAP)
    for column in REGION_TYPE_MAP.values():
        if column not in pivot.columns:
            pivot[column] = pd.NA

    name_by_respondent = (
        data[["respondent", "respondent-name"]]
        .dropna()
        .drop_duplicates("respondent")
        .set_index("respondent")["respondent-name"]
        .to_dict()
        if "respondent-name" in data.columns
        else {}
    )
    pivot["REGION_ID"] = pivot["respondent"]
    pivot["REGION_NAME"] = pivot["respondent"].map(name_by_respondent).fillna(pivot["respondent"])
    return pivot[["DATE_TIME_LOCAL", "REGION_ID", "REGION_NAME", "LOAD_MW", "LOAD_FORECAST_MW"]].sort_values(
        "DATE_TIME_LOCAL"
    )


def normalize_fuel_type_data(raw):
    if raw.empty:
        return pd.DataFrame(columns=["DATE_TIME_LOCAL", "REGION_ID", "SOLAR_MW", "WIND_MW", "GENERATION_MW"])

    data = raw.copy()
    data["DATE_TIME_LOCAL"] = pd.to_datetime(data["period"], errors="coerce")
    data["value"] = pd.to_numeric(data["value"], errors="coerce")
    data["fueltype"] = data["fueltype"].astype(str)
    data = data[data["fueltype"].isin(FUEL_TYPE_MAP)]

    pivot = data.pivot_table(
        values="value",
        index=["DATE_TIME_LOCAL", "respondent"],
        columns="fueltype",
        aggfunc="sum",
    ).reset_index()
    pivot = pivot.rename(columns=FUEL_TYPE_MAP)
    for column in FUEL_TYPE_MAP.values():
        if column not in pivot.columns:
            pivot[column] = 0.0

    pivot["GENERATION_MW"] = pivot["SOLAR_MW"].fillna(0.0) + pivot["WIND_MW"].fillna(0.0)
    pivot["REGION_ID"] = pivot["respondent"]
    return pivot[["DATE_TIME_LOCAL", "REGION_ID", "SOLAR_MW", "WIND_MW", "GENERATION_MW"]].sort_values(
        "DATE_TIME_LOCAL"
    )


def build_eia_dataset(start, end, respondent=DEFAULT_RESPONDENT, api_key=None):
    key = require_api_key(api_key)
    region_raw = fetch_eia_frame(
        "region-data",
        api_key=key,
        respondent=respondent,
        start=start,
        end=end,
        extra_facets={"type": list(REGION_TYPE_MAP)},
    )
    fuel_raw = fetch_eia_frame(
        "fuel-type-data",
        api_key=key,
        respondent=respondent,
        start=start,
        end=end,
        extra_facets={"fueltype": list(FUEL_TYPE_MAP)},
    )

    region = normalize_region_data(region_raw)
    fuel = normalize_fuel_type_data(fuel_raw)
    dataset = pd.merge(region, fuel, on=["DATE_TIME_LOCAL", "REGION_ID"], how="outer").sort_values("DATE_TIME_LOCAL")
    dataset["REGION_NAME"] = dataset["REGION_NAME"].fillna(respondent)
    dataset["NET_LOAD_MW"] = dataset["LOAD_MW"] - dataset["SOLAR_MW"].fillna(0.0) - dataset["WIND_MW"].fillna(0.0)
    dataset["SOLAR_SHARE_PERCENT"] = dataset["SOLAR_MW"] / dataset["LOAD_MW"] * 100.0
    return dataset[
        [
            "DATE_TIME_LOCAL",
            "REGION_ID",
            "REGION_NAME",
            "LOAD_MW",
            "LOAD_FORECAST_MW",
            "SOLAR_MW",
            "WIND_MW",
            "GENERATION_MW",
            "NET_LOAD_MW",
            "SOLAR_SHARE_PERCENT",
        ]
    ]


def main():
    parser = argparse.ArgumentParser(description="Download hourly EIA real grid data for an RTO respondent.")
    parser.add_argument("--start", required=True, help="Start hour, for example 2021-01-01T00.")
    parser.add_argument("--end", required=True, help="End hour, for example 2026-06-01T23.")
    parser.add_argument("--respondent", default=DEFAULT_RESPONDENT, help="EIA balancing authority/RTO id.")
    parser.add_argument("--output", default=str(DATA_DIR / "eia_ciso_2021_2026_generation_load.csv"))
    parser.add_argument("--api-key", default=None, help="EIA API key. Defaults to EIA_API_KEY.")
    args = parser.parse_args()

    dataset = build_eia_dataset(args.start, args.end, respondent=args.respondent, api_key=args.api_key)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    dataset.to_csv(output, index=False)
    print(f"Saved {len(dataset):,} EIA rows to {output}")


if __name__ == "__main__":
    main()
