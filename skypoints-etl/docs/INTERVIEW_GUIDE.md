# Live Technical Walkthrough & Interview Guide

## 5-Minute Demo Flow
1. **Architecture & Scale (1 min):** Walk through `docs/ARCHITECTURE.md` and `sql/01_ddl_snowflake.sql`. Explain why Raw stores everything as `VARCHAR`/`VARIANT` and how `CLUSTER BY (member_id)` handles billions of rows.
2. **Data Quality & Edge Cases (1 min):** Highlight the issues discovered in the sample CSVs (`2021-13-13` invalid date in AUS, missing DOB in USA, compact `6152022` dates) and show how `apply_data_quality_gates()` isolates bad records into the Dead-Letter Queue.
3. **Transformations & Country Migration (1.5 mins):** Explain `Age` and `Stale_Member` (>90 days since last flight) calculations, plus the `MERGE` + `QUALIFY ROW_NUMBER()` Latest-Record-Wins logic that deletes a member from their old country table when they migrate.
4. **JSON Redemption Flattening (0.5 min):** Show `LATERAL FLATTEN` in SQL and `parse_json_redemptions()` in Python, explaining how redemptions join back across country tables via a unified member view.
5. **Live Execution & Tests (1 min):** Run `pytest -v` and `skypoints-etl` in the terminal to show clean outputs in `outputs/`.

## Likely Follow-Up Questions
- **Q: How do you handle a member moving from India to the USA without losing history?**
  - *A:* In our current target design, the `MERGE` deletes the stale row from `TABLE_INDIA` and inserts the active profile into `TABLE_USA`. If historical tracking is required, we convert the target tables to **SCD Type 2** using `valid_from`, `valid_to`, and `is_current` flags instead of hard deletes.
- **Q: What happens if two updates arrive for the same member on the same day?**
  - *A:* We break ties using a source CDC sequence number or file ingestion timestamp (`ORDER BY last_flight_date DESC, source_updated_at DESC`).
