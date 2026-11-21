import argparse
import json
from pathlib import Path
from skypoints_etl.pipeline import SkyPointsETLPipeline


def main():
    parser = argparse.ArgumentParser(description="SkyPoints ETL Pipeline CLI")
    parser.add_argument("--data", default="data", help="Path to input data directory")
    parser.add_argument("--output", default="outputs", help="Path to output directory")
    parser.add_argument("--as-of", default="2026-11-21", help="Current reference date")

    args = parser.parse_args()
    data_dir = Path(args.data)
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    pipeline = SkyPointsETLPipeline(current_date=args.as_of)

    file_paths = {
        "IND": data_dir / "IND(in).csv",
        "USA": data_dir / "USA(in).csv",
        "AUS": data_dir / "AUS(Sheet1).csv",
    }

    existing_files = {k: v for k, v in file_paths.items() if Path(v).exists()}
    if not existing_files:
        print("No input member CSV files found in data directory.")
        return

    raw_df = pipeline.extract_member_files(existing_files)
    raw_df.to_csv(output_dir / "raw_normalized_members.csv", index=False)

    valid_df, dlq_df = pipeline.apply_data_quality_gates(raw_df)
    staged_df = pipeline.transform_staging(valid_df)
    final_df = pipeline.apply_latest_record_wins(staged_df)

    final_df.to_csv(output_dir / "current_members.csv", index=False)
    if not dlq_df.empty:
        dlq_df.to_csv(output_dir / "quarantined_dlq.csv", index=False)

    country_splits = pipeline.split_by_country(final_df)
    for country, cdf in country_splits.items():
        cdf.to_csv(output_dir / f"table_{country.lower()}.csv", index=False)

    json_file = data_dir / "sample_redemptions.json"
    if json_file.exists():
        with open(json_file, "r", encoding="utf-8") as jf:
            payloads = json.load(jf)
        redemptions_df = pipeline.parse_json_redemptions(payloads)
        redemptions_df.to_csv(output_dir / "flattened_redemptions.csv", index=False)

    print(f"ETL completed! Valid members: {len(final_df)}, Quarantined: {len(dlq_df)}. Outputs in '{output_dir}/'.")


if __name__ == "__main__":
    main()
