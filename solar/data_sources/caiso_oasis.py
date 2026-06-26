from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen
from urllib.error import HTTPError
import argparse
import io
import time
import zipfile

import pandas as pd


BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BASE_DIR / "data"
OASIS_URL = "https://oasis.caiso.com/oasisapi/SingleZip"
CAISO_TZ = "America/Los_Angeles"


def caiso_timestamp(timestamp):
    return timestamp.strftime("%Y%m%dT%H:%M-0000")


def fetch_oasis_csv(queryname, market_run_id, start, end, version=1, timeout=45, retries=4):
    query = {
        "resultformat": 6,
        "queryname": queryname,
        "version": version,
        "market_run_id": market_run_id,
        "startdatetime": caiso_timestamp(start),
        "enddatetime": caiso_timestamp(end),
    }
    url = f"{OASIS_URL}?{urlencode(query)}"
    for attempt in range(retries + 1):
        try:
            with urlopen(url, timeout=timeout) as response:
                payload = response.read()
            break
        except HTTPError as exc:
            if exc.code != 429 or attempt == retries:
                raise
            wait_seconds = 5 * (attempt + 1)
            print(f"CAISO rate limit hit; waiting {wait_seconds}s before retry...", flush=True)
            time.sleep(wait_seconds)

    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        csv_names = [name for name in archive.namelist() if name.lower().endswith(".csv")]
        if not csv_names:
            raise ValueError(f"No CSV found in CAISO OASIS response for {queryname} {market_run_id}")
        with archive.open(csv_names[0]) as csv_file:
            return pd.read_csv(csv_file)


def daterange_chunks(start_date, end_date, chunk_days=31):
    current = pd.Timestamp(start_date).tz_localize(CAISO_TZ).tz_convert("UTC")
    end = (pd.Timestamp(end_date) + pd.Timedelta(days=1)).tz_localize(CAISO_TZ).tz_convert("UTC")
    while current < end:
        next_day = min(current + pd.Timedelta(days=chunk_days), end)
        yield current.tz_convert("UTC").tz_localize(None), next_day.tz_convert("UTC").tz_localize(None)
        current = next_day


def normalize_load(load_df, market_run_id):
    data = load_df.copy()
    data = data[data["TAC_AREA_NAME"] == "CA ISO-TAC"]
    data["DATE_TIME_UTC"] = pd.to_datetime(data["INTERVALSTARTTIME_GMT"], utc=True)
    value_name = "LOAD_MW" if market_run_id == "ACTUAL" else "LOAD_FORECAST_MW"
    return (
        data[["DATE_TIME_UTC", "MW"]]
        .rename(columns={"MW": value_name})
        .sort_values("DATE_TIME_UTC")
        .drop_duplicates("DATE_TIME_UTC")
    )


def normalize_renewables(renewable_df, market_run_id):
    data = renewable_df.copy()
    data["DATE_TIME_UTC"] = pd.to_datetime(data["INTERVALSTARTTIME_GMT"], utc=True)
    value_name = "GENERATION_MW" if market_run_id == "ACTUAL" else "GENERATION_FORECAST_MW"
    pivot = data.pivot_table(
        values="MW",
        index="DATE_TIME_UTC",
        columns="RENEWABLE_TYPE",
        aggfunc="sum",
    ).reset_index()

    rename_map = {
        "Solar": "SOLAR_MW" if market_run_id == "ACTUAL" else "SOLAR_FORECAST_MW",
        "Wind": "WIND_MW" if market_run_id == "ACTUAL" else "WIND_FORECAST_MW",
    }
    pivot = pivot.rename(columns=rename_map)
    for column in rename_map.values():
        if column not in pivot.columns:
            pivot[column] = 0.0

    renewable_cols = list(rename_map.values())
    pivot[value_name] = pivot[renewable_cols].sum(axis=1)
    return pivot[["DATE_TIME_UTC", *renewable_cols, value_name]].sort_values("DATE_TIME_UTC")


def fetch_market_dataset(start_date, end_date, market_run_id, chunk_days=31, timeout=45):
    load_frames = []
    renewable_frames = []
    for start, end in daterange_chunks(start_date, end_date, chunk_days=chunk_days):
        print(f"Fetching CAISO {market_run_id} {start.date()} to {end.date()}...", flush=True)
        load_frames.append(
            normalize_load(fetch_oasis_csv("SLD_FCST", market_run_id, start, end, timeout=timeout), market_run_id)
        )
        renewable_frames.append(
            normalize_renewables(
                fetch_oasis_csv("SLD_REN_FCST", market_run_id, start, end, timeout=timeout),
                market_run_id,
            )
        )

    load_data = pd.concat(load_frames, ignore_index=True).drop_duplicates("DATE_TIME_UTC")
    renewable_data = pd.concat(renewable_frames, ignore_index=True).drop_duplicates("DATE_TIME_UTC")
    return pd.merge(load_data, renewable_data, on="DATE_TIME_UTC", how="outer").sort_values("DATE_TIME_UTC")


def build_caiso_dataset(start_date, end_date, include_dam=True, chunk_days=31, timeout=45):
    actual = fetch_market_dataset(start_date, end_date, "ACTUAL", chunk_days=chunk_days, timeout=timeout)
    dataset = actual
    if include_dam:
        dam = fetch_market_dataset(start_date, end_date, "DAM", chunk_days=chunk_days, timeout=timeout)
        dataset = pd.merge(dataset, dam, on="DATE_TIME_UTC", how="outer")

    dataset["DATE_TIME_LOCAL"] = dataset["DATE_TIME_UTC"].dt.tz_convert(CAISO_TZ).dt.tz_localize(None)
    dataset["REGION_ID"] = "caiso"
    dataset["REGION_NAME"] = "CAISO"
    dataset["NET_LOAD_MW"] = dataset.get("LOAD_MW", 0) - dataset.get("SOLAR_MW", 0) - dataset.get("WIND_MW", 0)
    dataset["SOLAR_SHARE_PERCENT"] = dataset.get("SOLAR_MW", 0) / dataset.get("LOAD_MW", pd.NA) * 100

    ordered = [
        "DATE_TIME_UTC",
        "DATE_TIME_LOCAL",
        "REGION_ID",
        "REGION_NAME",
        "LOAD_MW",
        "LOAD_FORECAST_MW",
        "SOLAR_MW",
        "SOLAR_FORECAST_MW",
        "WIND_MW",
        "WIND_FORECAST_MW",
        "GENERATION_MW",
        "GENERATION_FORECAST_MW",
        "NET_LOAD_MW",
        "SOLAR_SHARE_PERCENT",
    ]
    for column in ordered:
        if column not in dataset.columns:
            dataset[column] = pd.NA
    return dataset[ordered].sort_values("DATE_TIME_UTC")


def main():
    parser = argparse.ArgumentParser(description="Fetch public CAISO OASIS load and renewable generation data.")
    parser.add_argument("--start", required=True, help="Start date in YYYY-MM-DD format, California local date.")
    parser.add_argument("--end", required=True, help="End date in YYYY-MM-DD format, California local date.")
    parser.add_argument(
        "--output",
        default=str(DATA_DIR / "caiso_generation_load.csv"),
        help="Output CSV path.",
    )
    parser.add_argument("--actual-only", action="store_true", help="Skip DAM forecast columns.")
    parser.add_argument("--chunk-days", type=int, default=31, help="Number of local days per CAISO request.")
    parser.add_argument("--timeout", type=int, default=45, help="Request timeout in seconds.")
    args = parser.parse_args()

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    dataset = build_caiso_dataset(
        args.start,
        args.end,
        include_dam=not args.actual_only,
        chunk_days=args.chunk_days,
        timeout=args.timeout,
    )
    dataset.to_csv(output, index=False)
    print(f"Saved {len(dataset):,} CAISO rows to {output}")


if __name__ == "__main__":
    main()
