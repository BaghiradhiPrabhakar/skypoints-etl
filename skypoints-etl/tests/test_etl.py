import pandas as pd
import pytest
from skypoints_etl.pipeline import SkyPointsETLPipeline


@pytest.fixture
def pipeline():
    return SkyPointsETLPipeline(current_date="2026-11-21")


def test_age_calculation(pipeline):
    data = pd.DataFrame(
        {
            "member_id": ["IND_1"],
            "member_name": ["Test User"],
            "dob": ["1990-01-01"],
            "last_flight_date": ["2026-01-01"],
            "enrollment_date": ["2020-01-01"],
        }
    )
    result = pipeline.transform_staging(data)
    assert result.loc[0, "age"] == 36


def test_stale_member_flag(pipeline):
    data = pd.DataFrame(
        {
            "member_id": ["IND_1", "IND_2"],
            "member_name": ["Active", "Stale"],
            "dob": ["1990-01-01", "1990-01-01"],
            "last_flight_date": ["2026-11-11", "2025-01-01"],
            "enrollment_date": ["2020-01-01", "2020-01-01"],
        }
    )
    result = pipeline.transform_staging(data)
    assert bool(result.loc[0, "stale_member"]) is False
    assert bool(result.loc[1, "stale_member"]) is True


def test_data_quality_quarantines_bad_dates(pipeline):
    data = pd.DataFrame(
        {
            "member_id": ["AUS_1", "AUS_2"],
            "member_name": ["Mike", "Jonnathan"],
            "dob": [None, "1997-12-13"],
            "enrollment_date": ["2022-05-11", "2021-13-13"],
            "last_flight_date": ["2022-08-01", "2022-01-05"],
        }
    )
    valid_df, dlq_df = pipeline.apply_data_quality_gates(data)
    assert len(valid_df) == 1
    assert len(dlq_df) == 1
    assert dlq_df.iloc[0]["member_id"] == "AUS_2"


def test_latest_record_wins(pipeline):
    data = pd.DataFrame(
        {
            "member_id": ["M_123", "M_123"],
            "member_name": ["John Doe", "John Doe"],
            "country": ["USA", "IND"],
            "last_flight_date": [pd.to_datetime("2024-01-01"), pd.to_datetime("2025-06-01")],
            "enrollment_date": [pd.to_datetime("2020-01-01"), pd.to_datetime("2020-01-01")],
        }
    )
    result = pipeline.apply_latest_record_wins(data)
    assert len(result) == 1
    assert result.iloc[0]["country"] == "IND"


def test_json_redemption_parsing(pipeline):
    sample_json = [
        {
            "member id": "223457",
            "feed_date": "20240115",
            "redemptions": [
                {
                    "txn_id": "RX10091",
                    "txn_date": "20240110",
                    "partner": "AeroLink",
                    "miles_redeemed": 12000,
                    "status": "COMPLETED",
                }
            ],
        }
    ]
    df_redemptions = pipeline.parse_json_redemptions(sample_json)
    assert len(df_redemptions) == 1
    assert df_redemptions.loc[0, "txn_id"] == "RX10091"
    assert df_redemptions.loc[0, "miles_redeemed"] == 12000
