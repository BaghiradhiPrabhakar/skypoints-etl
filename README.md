# SkyPoints Loyalty ETL Pipeline

Production-grade Data Engineering assessment solution for processing multi-country loyalty member profiles and semi-structured partner redemption feeds at scale.

## 📂 Project Navigation
All project source code, Snowflake DDLs, unit tests, and architecture documentation are located inside the **`skypoints-etl/`** directory:

* **[`skypoints-etl/README.md`](./skypoints-etl/README.md)** — Full setup, CLI execution instructions, and project overview
* **[`skypoints-etl/src/skypoints_etl/`](./skypoints-etl/src/skypoints_etl/)** — Python ETL pipeline, DQ quarantine gates, and CLI
* **[`skypoints-etl/sql/`](./skypoints-etl/sql/)** — Idempotent Snowflake DDLs and set-based `MERGE` transformation scripts
* **[`skypoints-etl/tests/`](./skypoints-etl/tests/)** — Automated Pytest unit test suite
* **[`skypoints-etl/docs/`](./skypoints-etl/docs/)** — Medallion architecture blueprint and interview walkthrough guide
