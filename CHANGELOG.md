# Changelog

## Unreleased

- English documentation, contributor guidance, technical messages and default panel language; retain explicit Polish localization.
- Isolated Docker Compose integration tests, a `stable` / `dev` GitHub Actions matrix and weekly runs.
- API scenarios covering purchases, aliases, deduplication, restarts, Options Flow, panel registration and authorization.
- JUnit, HA version, image ID and logs as CI artifacts.
- Corrected administrator authorization and asynchronous WebSocket decorator ordering.
- Handle native add events arriving after a generic state notification, preserving reliable addition order for deduplication.
- Avoid double-unsubscribing the HA stop listener during shutdown.

## 0.1.0 — 2026-10-25

- Initial implementation, HA domain `pax0r_listkeeper`.
- Native list reconciliation, permanent purchase history and one-hour corrections.
- Safe UID-based deduplication with durable intents and retry handling.
- Name catalog, historical merges and explicit splitting/reassignment.
- SQLAlchemy 2, Alembic migrations 001/002 and backend-specific storage isolation.
- Administrator WebSocket API, local panel, statistics, export and explicit deletion.
- Config/Options Flow, localization, tests and CI.
- See the validation report for checks actually executed; configuration alone does not establish compatibility.
