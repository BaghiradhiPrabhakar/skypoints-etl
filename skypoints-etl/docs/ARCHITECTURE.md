# SkyPoints ETL Architecture Blueprint

## 1. Overview & Scale Design (Billions of Records/Day)
To ingest and process billions of daily profile updates and redemption transactions without bottlenecking, the architecture adopts a **Medallion Pattern (Raw -> Staging -> Target)** on cloud object storage (S3/GCS) and Snowflake:

- **Ingestion:** Snowpipe / auto-ingest streaming micro-batches from cloud storage into append-only Raw tables (`VARIANT` for JSON, `VARCHAR` for flat files).
- **Clustering & Pruning:** Target tables are clustered by `member_id` (and `feed_date` for redemptions) so `MERGE` operations prune >99% of micro-partitions.
- **Idempotency:** All SQL merges and Python deduplication steps are deterministic and safely re-runnable.

## 2. Sample Data Assumptions & Edge Cases
- **Schema Harmonization:** Upstream feeds (`IND`, `USA`, `AUS`) have distinct column names and date formats (`M/D/YYYY`, `MMDDYYYY`, `YYYY-MM-DD`). The ingestion layer normalizes them into a canonical schema.
- **Invalid Dates:** Records with impossible dates (such as `2021-13-13` in the Australia extract) are caught at the Data Quality gate and quarantined into `MEMBER_DLQ` rather than crashing the batch.
- **ID Collision Prevention:** Because IDs `1–3` repeat independently in each country sample file, IDs are namespaced by source country (`IND_1`, `USA_1`, `AUS_1`) during extraction.
