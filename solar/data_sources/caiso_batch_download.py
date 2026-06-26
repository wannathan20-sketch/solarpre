from pathlib import Path
import argparse

import pandas as pd

from caiso_oasis import build_caiso_dataset


BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BASE_DIR / "data"


def month_windows(start_date, end_date):
    start = pd.Timestamp(start_date)
    end = pd.Timestamp(end_date)
    current = pd.Timestamp(year=start.year, month=start.month, day=1)
    while current <= end:
        next_month = current + pd.offsets.MonthBegin(1)
        window_start = max(current, start)
        window_end = min(next_month - pd.Timedelta(days=1), end)
        yield window_start.date().isoformat(), window_end.date().isoformat()
        current = next_month


def main():
    parser = argparse.ArgumentParser(description="Download CAISO OASIS data month by month.")
    parser.add_argument("--start", required=True, help="Start date in YYYY-MM-DD format.")
    parser.add_argument("--end", required=True, help="End date in YYYY-MM-DD format.")
    parser.add_argument("--output-dir", default=str(DATA_DIR / "caiso_monthly"))
    parser.add_argument("--combined-output", default=str(DATA_DIR / "caiso_generation_load.csv"))
    parser.add_argument("--chunk-days", type=int, default=7)
    parser.add_argument("--timeout", type=int, default=45)
    parser.add_argument("--actual-only", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    monthly_files = []
    for start, end in month_windows(args.start, args.end):
        monthly_file = output_dir / f"caiso_{start[:7]}.csv"
        monthly_files.append(monthly_file)
        if monthly_file.exists() and not args.overwrite:
            print(f"Skipping existing {monthly_file}", flush=True)
            continue

        print(f"Downloading CAISO {start} to {end}...", flush=True)
        dataset = build_caiso_dataset(
            start,
            end,
            include_dam=not args.actual_only,
            chunk_days=args.chunk_days,
            timeout=args.timeout,
        )
        dataset.to_csv(monthly_file, index=False)
        print(f"Saved {len(dataset):,} rows to {monthly_file}", flush=True)

    frames = []
    for monthly_file in monthly_files:
        if monthly_file.exists():
            frames.append(pd.read_csv(monthly_file))

    if frames:
        combined = pd.concat(frames, ignore_index=True)
        combined = combined.drop_duplicates("DATE_TIME_UTC").sort_values("DATE_TIME_UTC")
        combined_output = Path(args.combined_output)
        combined_output.parent.mkdir(parents=True, exist_ok=True)
        combined.to_csv(combined_output, index=False)
        print(f"Saved combined {len(combined):,} rows to {combined_output}", flush=True)


if __name__ == "__main__":
    main()
