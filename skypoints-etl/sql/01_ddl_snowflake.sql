-- =========================================================================
-- SKYPOINTS GLOBAL LOYALTY PROGRAM - SNOWFLAKE DDL SCRIPTS
-- =========================================================================

CREATE DATABASE IF NOT EXISTS SKYPOINTS_DB;
CREATE SCHEMA IF NOT EXISTS SKYPOINTS_DB.RAW;
CREATE SCHEMA IF NOT EXISTS SKYPOINTS_DB.STAGING;
CREATE SCHEMA IF NOT EXISTS SKYPOINTS_DB.TARGET;

-- 1. RAW / LANDING LAYER
CREATE OR REPLACE TABLE SKYPOINTS_DB.RAW.MEMBER_PROFILE_LANDING (
    member_name      VARCHAR(255),
    member_id        VARCHAR(50),
    enrollment_date  VARCHAR(50),
    last_flight_date VARCHAR(50),
    tier_code        VARCHAR(10),
    agent_name       VARCHAR(255),
    state            VARCHAR(50),
    country          VARCHAR(50),
    post_code        VARCHAR(50),
    dob              VARCHAR(50),
    active_member    VARCHAR(10),
    source_file      VARCHAR(255),
    load_timestamp   TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP()
);

CREATE OR REPLACE TABLE SKYPOINTS_DB.RAW.REDEMPTION_FEED_LANDING (
    feed_payload     VARIANT,
    ingest_timestamp TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP()
);

-- 2. STAGING & QUARANTINE LAYER
CREATE OR REPLACE TABLE SKYPOINTS_DB.STAGING.STG_MEMBER_PROFILES (
    member_id        VARCHAR(50) NOT NULL,
    member_name      VARCHAR(255) NOT NULL,
    enrollment_date  DATE NOT NULL,
    last_flight_date DATE,
    tier_code        VARCHAR(10),
    agent_name       VARCHAR(255),
    state            VARCHAR(50),
    country          VARCHAR(50) NOT NULL,
    post_code        INTEGER,
    dob              DATE,
    active_member    CHAR(1),
    age              INTEGER,
    stale_member     BOOLEAN,
    batch_id         VARCHAR(50),
    updated_at       TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP()
);

CREATE OR REPLACE TABLE SKYPOINTS_DB.STAGING.MEMBER_DLQ (
    raw_record       VARIANT,
    error_reason     VARCHAR(1000),
    failed_at        TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP()
);

-- 3. COUNTRY TARGET TABLES (Clustered for billion-row performance)
CREATE OR REPLACE TABLE SKYPOINTS_DB.TARGET.TABLE_INDIA (
    member_id        VARCHAR(50) NOT NULL,
    member_name      VARCHAR(255),
    enrollment_date  DATE,
    last_flight_date DATE,
    tier_code        VARCHAR(10),
    agent_name       VARCHAR(255),
    state            VARCHAR(50),
    country          VARCHAR(50),
    post_code        INTEGER,
    dob              DATE,
    active_member    CHAR(1),
    age              INTEGER,
    stale_member     BOOLEAN,
    updated_at       TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
    CONSTRAINT pk_india_member PRIMARY KEY (member_id)
)
CLUSTER BY (member_id);

CREATE OR REPLACE TABLE SKYPOINTS_DB.TARGET.TABLE_USA LIKE SKYPOINTS_DB.TARGET.TABLE_INDIA;
CREATE OR REPLACE TABLE SKYPOINTS_DB.TARGET.TABLE_AUS LIKE SKYPOINTS_DB.TARGET.TABLE_INDIA;

-- 4. FLATTENED REDEMPTION TRANSACTIONS
CREATE OR REPLACE TABLE SKYPOINTS_DB.TARGET.FLATTENED_REDEMPTIONS (
    txn_id           VARCHAR(50) NOT NULL,
    member_id        VARCHAR(50) NOT NULL,
    feed_date        DATE,
    txn_date         DATE,
    partner          VARCHAR(100),
    miles_redeemed   NUMBER(18,2),
    status           VARCHAR(50),
    loaded_at        TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
    CONSTRAINT pk_txn PRIMARY KEY (txn_id)
)
CLUSTER BY (feed_date, member_id);
