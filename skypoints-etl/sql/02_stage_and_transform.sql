-- =========================================================================
-- SKYPOINTS - SET-BASED TRANSFORMATIONS, DEDUPLICATION & JSON FLATTENING
-- =========================================================================

-- 1. Route invalid records to Dead-Letter Queue (DLQ)
INSERT INTO SKYPOINTS_DB.STAGING.MEMBER_DLQ (raw_record, error_reason)
SELECT
    OBJECT_CONSTRUCT(*),
    CASE
        WHEN member_id IS NULL OR TRIM(member_id) = '' THEN 'Missing mandatory member_id'
        WHEN member_name IS NULL OR TRIM(member_name) = '' THEN 'Missing mandatory member_name'
        WHEN TRY_TO_DATE(enrollment_date, 'YYYYMMDD') IS NULL THEN 'Invalid enrollment_date'
        ELSE 'Validation failure'
    END
FROM SKYPOINTS_DB.RAW.MEMBER_PROFILE_LANDING
WHERE member_id IS NULL
   OR TRIM(member_id) = ''
   OR member_name IS NULL
   OR TRIM(member_name) = ''
   OR TRY_TO_DATE(enrollment_date, 'YYYYMMDD') IS NULL;

-- 2. Load valid records into Staging with derived Age & Stale_Member flag
INSERT INTO SKYPOINTS_DB.STAGING.STG_MEMBER_PROFILES (
    member_id, member_name, enrollment_date, last_flight_date, tier_code,
    agent_name, state, country, post_code, dob, active_member, age, stale_member
)
SELECT
    TRIM(member_id),
    TRIM(member_name),
    TRY_TO_DATE(enrollment_date, 'YYYYMMDD') AS enrollment_date,
    TRY_TO_DATE(last_flight_date, 'YYYYMMDD') AS last_flight_date,
    TRIM(tier_code),
    TRIM(agent_name),
    TRIM(state),
    UPPER(TRIM(country)),
    TRY_TO_NUMBER(post_code),
    TRY_TO_DATE(dob, 'MMDDYYYY') AS dob,
    TRIM(active_member),
    DATEDIFF('year', TRY_TO_DATE(dob, 'MMDDYYYY'), CURRENT_DATE()) AS age,
    IFF(DATEDIFF('day', TRY_TO_DATE(last_flight_date, 'YYYYMMDD'), CURRENT_DATE()) > 90, TRUE, FALSE) AS stale_member
FROM SKYPOINTS_DB.RAW.MEMBER_PROFILE_LANDING
WHERE member_id IS NOT NULL
  AND TRIM(member_id) <> ''
  AND member_name IS NOT NULL
  AND TRIM(member_name) <> ''
  AND TRY_TO_DATE(enrollment_date, 'YYYYMMDD') IS NOT NULL;

-- 3. Latest-Record-Wins Deduplication & Merge into Country Target (Example: INDIA)
MERGE INTO SKYPOINTS_DB.TARGET.TABLE_INDIA tgt
USING (
    SELECT *
    FROM SKYPOINTS_DB.STAGING.STG_MEMBER_PROFILES
    QUALIFY ROW_NUMBER() OVER (
        PARTITION BY member_id
        ORDER BY last_flight_date DESC NULLS LAST, enrollment_date DESC
    ) = 1
) src
ON tgt.member_id = src.member_id
WHEN MATCHED AND src.country IN ('IND', 'INDIA') THEN UPDATE SET
    tgt.member_name = src.member_name,
    tgt.last_flight_date = src.last_flight_date,
    tgt.tier_code = src.tier_code,
    tgt.age = src.age,
    tgt.stale_member = src.stale_member,
    tgt.updated_at = CURRENT_TIMESTAMP()
WHEN MATCHED AND src.country NOT IN ('IND', 'INDIA') THEN
    -- Member migrated out of India
    DELETE
WHEN NOT MATCHED AND src.country IN ('IND', 'INDIA') THEN INSERT (
    member_id, member_name, enrollment_date, last_flight_date, tier_code,
    agent_name, state, country, post_code, dob, active_member, age, stale_member
) VALUES (
    src.member_id, src.member_name, src.enrollment_date, src.last_flight_date, src.tier_code,
    src.agent_name, src.state, src.country, src.post_code, src.dob, src.active_member, src.age, src.stale_member
);

-- 4. Flatten semi-structured JSON redemption feed
MERGE INTO SKYPOINTS_DB.TARGET.FLATTENED_REDEMPTIONS tgt
USING (
    SELECT
        f.value:txn_id::VARCHAR AS txn_id,
        COALESCE(p.feed_payload:"member id"::VARCHAR, p.feed_payload:member_id::VARCHAR) AS member_id,
        TRY_TO_DATE(p.feed_payload:feed_date::VARCHAR, 'YYYYMMDD') AS feed_date,
        TRY_TO_DATE(f.value:txn_date::VARCHAR, 'YYYYMMDD') AS txn_date,
        f.value:partner::VARCHAR AS partner,
        f.value:miles_redeemed::NUMBER(18,2) AS miles_redeemed,
        f.value:status::VARCHAR AS status
    FROM SKYPOINTS_DB.RAW.REDEMPTION_FEED_LANDING p,
    LATERAL FLATTEN(input => p.feed_payload:redemptions) f
    QUALIFY ROW_NUMBER() OVER (PARTITION BY txn_id ORDER BY feed_date DESC) = 1
) src
ON tgt.txn_id = src.txn_id
WHEN MATCHED THEN UPDATE SET
    tgt.status = src.status,
    tgt.miles_redeemed = src.miles_redeemed,
    tgt.loaded_at = CURRENT_TIMESTAMP()
WHEN NOT MATCHED THEN INSERT (
    txn_id, member_id, feed_date, txn_date, partner, miles_redeemed, status
) VALUES (
    src.txn_id, src.member_id, src.feed_date, src.txn_date, src.partner, src.miles_redeemed, src.status
);
