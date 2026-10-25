# Changelog

## Unreleased

- Add pinned pre-commit hooks for Ruff and file validation; CI uses the same configuration. Leave routine agent linting/formatting to hooks and CI.
- Manage explicitly opted-in Shopping List and Local To-do entities with independent catalogs, aliases, history, statistics, exports and deletion. Add a persistent list context selector to the panel and scoped WebSocket commands.
- Add schema revision `003` and config-entry version 2, retaining the original catalog and history during migration. Deselecting lists retains their data; an empty selection pauses processing.
- Subscribe to item changes, including completed-task renames that leave the active count unchanged. Preserve Local To-do entries with conflicting due dates or descriptions.
- Pin CI runners to Ubuntu 24.04 and update checkout, setup-node, setup-uv and artifact actions to versions using Node 24.
- Replace global merge/move selectors with explicit dialogs, a selection toolbar, per-row actions and expandable catalog instructions in English and Polish.
- Clean existing completed-only and mixed-status duplicate groups, preferring an active survivor and retaining purchase history. Delete multiple duplicates in one validated batch.
- Match accent variants such as `Mydło` / `mydlo`, automatically linking existing catalog identities with audit records while preserving original names and purchase IDs.
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
