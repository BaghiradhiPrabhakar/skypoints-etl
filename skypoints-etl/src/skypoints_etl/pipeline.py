import json
import logging
from pathlib import Path
import numpy as np
import pandas as pd

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class SkyPointsETLPipeline:
    def __init__(self, current_date=None):
        self.current_date = (
            pd.to_datetime(current_date)
            if current_date
            else pd.to_datetime("2026-11-21")
        )

    def _parse_flexible_date(self, series: pd.Series) -> pd.Series:
        """Parses standard dates as well as compact MMDDYYYY integer strings."""
        def parse_single(val):
            if pd.isna(val) or str(val).strip().upper() in ("", "NULL", "NAN"):
                return pd.NaT
            s = str(val).strip()
            # Handle numeric compact strings like 6152022 or 12282021
            if s.isdigit():
                s = s.zfill(8)
                try:
                    return pd.to_datetime(s, format="%m%d%Y")
                except ValueError:
                    return pd.NaT
            try:
                return pd.to_datetime(s)
            except ValueError:
                return pd.NaT

        return series.apply(parse_single)

    def extract_member_files(self, file_paths: dict) -> pd.DataFrame:
        """Extracts and standardizes member profiles from multi-format country CSVs."""
        dfs = []

        if "IND" in file_paths:
            df_ind = pd.read_csv(file_paths["IND"])
            df_ind = df_ind.rename(
                columns={
                    "ID": "raw_id",
                    "Name": "member_name",
                    "DOB": "dob",
                    "TierCode": "tier_code",
                    "EnrollmentDate": "enrollment_date",
                    "Flight Date": "last_flight_date",
                    "Individual or Corporate": "member_type",
                }
            )
            df_ind["country"] = "IND"
            df_ind["member_id"] = "IND_" + df_ind["raw_id"].astype(str)
            dfs.append(df_ind)

        if "USA" in file_paths:
            df_usa = pd.read_csv(file_paths["USA"])
            df_usa = df_usa.rename(
                columns={
                    "ID": "raw_id",
                    "Name": "member_name",
                    "TierCode": "tier_code",
                    "EnrollmentDate": "enrollment_date",
                    "FlightDate": "last_flight_date",
                }
            )
            df_usa["country"] = "USA"
            df_usa["dob"] = np.nan
            df_usa["member_type"] = np.nan
            df_usa["member_id"] = "USA_" + df_usa["raw_id"].astype(str)
            dfs.append(df_usa)

        if "AUS" in file_paths:
            df_aus = pd.read_csv(file_paths["AUS"])
            df_aus = df_aus.rename(
                columns={
                    "Unique ID": "raw_id",
                    "Member Name": "member_name",
                    "Tier Type": "tier_code",
                    "Date of Birth": "dob",
                    "Date of Enrollment": "enrollment_date",
                    "Date of Flight": "last_flight_date",
                }
            )
            df_aus["country"] = "AUS"
            df_aus["member_type"] = np.nan
            df_aus["member_id"] = "AUS_" + df_aus["raw_id"].astype(str)
            dfs.append(df_aus)

        if not dfs:
            return pd.DataFrame()

        combined_df = pd.concat(dfs, ignore_index=True)
        logger.info(f"Extracted {len(combined_df)} raw records across all country feeds.")
        return combined_df

    def apply_data_quality_gates(self, df: pd.DataFrame):
        """Validates mandatory fields and date parsing; routes invalid rows to DLQ."""
        df = df.copy()
        df["parsed_enrollment_date"] = self._parse_flexible_date(df["enrollment_date"])
        df["parsed_last_flight_date"] = self._parse_flexible_date(df["last_flight_date"])
        df["parsed_dob"] = self._parse_flexible_date(df["dob"])

        reasons = []
        for _, row in df.iterrows():
            row_reasons = []
            if pd.isna(row.get("member_id")) or str(row.get("member_id")).strip() == "":
                row_reasons.append("Missing mandatory member_id")
            if pd.isna(row.get("member_name")) or str(row.get("member_name")).strip() == "":
                row_reasons.append("Missing mandatory member_name")
            if pd.isna(row["parsed_enrollment_date"]):
                row_reasons.append(f"Invalid or missing enrollment_date: {row.get('enrollment_date')}")
            reasons.append("; ".join(row_reasons))

        df["dq_error"] = reasons
        valid_mask = df["dq_error"] == ""

        valid_df = df[valid_mask].drop(columns=["dq_error"]).copy()
        dlq_df = df[~valid_mask].copy()

        # Replace raw date strings with parsed dates in valid_df
        valid_df["enrollment_date"] = valid_df.pop("parsed_enrollment_date")
        valid_df["last_flight_date"] = valid_df.pop("parsed_last_flight_date")
        valid_df["dob"] = valid_df.pop("parsed_dob")

        if not dlq_df.empty:
            logger.warning(f"Quarantined {len(dlq_df)} invalid records to DLQ.")

        return valid_df, dlq_df

    def transform_staging(self, df: pd.DataFrame) -> pd.DataFrame:
        """Derives Age and Stale_Member flag."""
        df = df.copy()
        for col in ["enrollment_date", "last_flight_date", "dob"]:
            if col in df.columns and not pd.api.types.is_datetime64_any_dtype(df[col]):
                df[col] = self._parse_flexible_date(df[col])

        df["age"] = ((self.current_date - df["dob"]).dt.days // 365.25).astype("Int64")
        days_since_flight = (self.current_date - df["last_flight_date"]).dt.days
        df["stale_member"] = (days_since_flight > 90).fillna(False)
        return df

    def apply_latest_record_wins(self, df: pd.DataFrame) -> pd.DataFrame:
        """Applies latest-record-wins deduplication across country migrations."""
        df = df.sort_values(
            by=["member_id", "last_flight_date", "enrollment_date"],
            ascending=[True, False, False],
            na_position="last",
        )
        deduped_df = df.drop_duplicates(subset=["member_id"], keep="first").copy()
        logger.info(
            f"Deduplicated from {len(df)} to {len(deduped_df)} records via Latest-Record-Wins."
        )
        return deduped_df

    def split_by_country(self, df: pd.DataFrame) -> dict:
        """Splits deduplicated member records into per-country DataFrames."""
        return {
            country: group.copy()
            for country, group in df.groupby("country")
        }

    def parse_json_redemptions(self, json_payloads: list) -> pd.DataFrame:
        """Flattens semi-structured JSON redemption feeds."""
        flattened_rows = []
        for payload in json_payloads:
            member_id = payload.get("member id") or payload.get("member_id")
            feed_date = payload.get("feed_date")
            for txn in payload.get("redemptions", []):
                flattened_rows.append(
                    {
                        "member_id": member_id,
                        "feed_date": feed_date,
                        "txn_id": txn.get("txn_id"),
                        "txn_date": txn.get("txn_date"),
                        "partner": txn.get("partner"),
                        "miles_redeemed": txn.get("miles_redeemed"),
                        "status": txn.get("status"),
                    }
                )
        return pd.DataFrame(flattened_rows)
