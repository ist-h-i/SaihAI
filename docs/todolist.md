# CI Follow-ups (M3 P2)

Per issue constraints, workflow files are unchanged. Suggested CI steps:

- frontend build: `npm --prefix frontend run build`
- backend validation: `python -m compileall backend/app`
- migrations smoke check (optional): `python backend/scripts/db_tool.py migrate_up`

Runtime notes:
- External actions default to mock providers (`EMAIL_PROVIDER=mock`, `CALENDAR_PROVIDER=mock`).
- Weekly report ingestion reads `backend/app/data/weekly_reports_source.json` (run `python backend/scripts/ingest_weekly_reports.py`).
