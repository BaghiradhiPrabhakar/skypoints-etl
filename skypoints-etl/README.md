# SkyPoints Data Engineering Assessment

End-to-end demonstration for the Incubyte Data Engineer technical assessment.

## Quick start
Requires Python 3.11+.

```bash
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate
pip install -e ".[dev]"
pytest -v
skypoints-etl --data data --output outputs --as-of 2026-11-21
```

Or run without installing the console script:
```bash
PYTHONPATH=src python -m skypoints_etl.cli --data data --output outputs --as-of 2026-11-21
```

## Repository layout
- `src/skypoints_etl/`: Python ingestion, normalization, validation, enrichment, deduplication, routing, and JSON flattening.
- `sql/`: Snowflake DDL and set-based transformation scripts.
- `data/`: Sample extracts (`IND(in).csv`, `USA(in).csv`, `AUS(Sheet1).csv`, and `sample_redemptions.json`).
- `tests/`: Automated unit test suite.
- `docs/ARCHITECTURE.md`: Architecture, assumptions, scale, and operational design.
- `docs/INTERVIEW_GUIDE.md`: Walkthrough and likely interview questions.
