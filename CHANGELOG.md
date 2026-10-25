# Changelog

## Unreleased

- Add the MIT license and document GitHub topics required for HACS publication.
- Remove one-off bootstrap, validation and diagnostic scripts. Keep container orchestration under `tests/containers` and run repository checks through pytest.

- Fix hassfest manifest ordering, rely on HA's own SQLAlchemy dependency, and declare config-entry-only configuration through HA's validation helper.

- Align the project Python range with HA's minimum (`>=3.14.2,<3.15`), pin CI/development to Python 3.14.9 and uv 0.13.5, and lock dependency installation across all groups.
- Include the matching HA frontend package in the in-process test environment; verify clean Linux installs for both ordinary and HA test groups.

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
