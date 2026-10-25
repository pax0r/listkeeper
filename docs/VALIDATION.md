# Validation record

This file records checks actually executed, separately from prepared CI configuration.

## Previous local baseline

October 25, 2026; Windows, Python 3.14.0, SQLAlchemy 2.0.54, Alembic 1.20.0, pytest 8.4.2, Ruff 0.16.5, Node.js 22.22.3, aiohttp 3.14.4.

| Check | Recorded result |
| --- | --- |
| `python -m pytest -q --basetemp .pytest-tmp-containers-4` | 65 passed, 13 environment-dependent skips |
| Ruff lint and formatting | Passed |
| `python scripts/check_structure.py` | Packaging, JSON and domain boundaries passed |
| `npm test` | 4 passed |
| `npm run check` | Passed |
| `docker compose -f compose.ha-test.yml config --quiet` | Passed |
| Container runner `--help` | Passed |

Coverage includes normalization, ambiguity, UID preservation, duplicate convergence, event loops, purchases, 15/60/61-minute corrections, cycles, restart/offline behavior, name merges/moves, local dates and DST, statistics filters, export/deletion, transaction rollback, foreign keys, uniqueness, migrations and concurrent UoW calls.

Failure tests cover unavailable SQL, failed deletion, a crash after HA deletion but before SQL acknowledgement, and stale intents after rename or split. HA contract tests use explicit fakes, including UID/name collisions and Recorder compatibility changes.

Local aiohttp fixtures exercise real HTTP/WebSocket transport, deadlines, redacted errors and container isolation checks. WebSocket scheduling contract tests verify administrator execution and rejection before work starts. JavaScript tests cover escaping, frequency presentation, sorting and transport; they do not establish browser compatibility.

The 13 skips comprise 11 container cases, the in-process HA module and one server SQL test. Skipped checks are not passed checks.

## Current integration run

Executed on October 25, 2026 using Docker Desktop Linux containers and the final corrected code:

| Suite | Environment | Result |
| --- | --- | --- |
| Local Python | Python 3.14.0, SQLite | 66 passed; 13 explicit external-environment skips |
| Frontend helpers | Node.js 22.22.3 | 5 passed |
| Real HA container | `stable`: HA `2026.10.4`, Python 3.14.9, SQLite | 11 passed in 9.62 seconds |
| Real HA container | `dev`: HA `2026.11.0.dev202610250226`, Python 3.14.9, SQLite | 11 passed in 10.12 seconds |
| Ruff lint/format, structure check and frontend syntax | Local workspace | Passed |

The ordinary Python run skips Docker cases unless explicitly requested; both separate Docker runs executed all 11 cases with no skips. Their test projects were `listkeeper-test-stable-verified` and `listkeeper-test-dev-verified`. JUnit, exact image IDs, HA versions and logs are retained under `test-results/<project>/` locally. The runner removed both containers and their test volumes afterward.

Real execution exposed an addition-event ordering defect: a generic state notification could persist an item before its native add event, losing reliable addition order. Reconciliation now promotes that existing snapshot when the trusted UID-specific event arrives. A dedicated regression test passes. Shutdown logs also exposed double removal of a one-time stop listener; runtime now owns a regular listener and unsubscribes once.

The first corrected stable run had nine passes and two failures in test assumptions, not product behavior: HA's manifest singleton guard returns `single_instance_allowed`, and user creation returns a nested `user` object. Tests now follow those actual contracts. Both final runs passed completely.

Final logs contain expected errors from deliberate invalid-confirmation and unauthorized-user scenarios, plus HA's normal custom-integration warning. There are no shutdown listener tracebacks or synchronization failures in the final runs. The host cache warning from an intermediate run was eliminated by disabling pytest's cache provider for container tests.

## Checks requiring separate evidence

- Other HA versions: only the exact stable and development builds listed above have been exercised.
- In-process HA: tracked separately from the real-container scenarios below; it requires the matching frontend package as well as the core fixture dependency.
- PostgreSQL, MySQL and MariaDB: isolated servers and `SI_TEST_DATABASE_URL` required.
- hassfest and HACS: jobs prepared; no local success claimed.
- Browser rendering, interactions, themes and mobile layout: not verified by API or helper tests.

The [API review](HA_API_REVIEW.md) records documentation/source inspection, which does not substitute for runtime verification. No GitHub/HACS publication has been performed from this workspace.

## CI dependency bootstrap correction

The reported GitHub run failed before executing tests: `requires-python = ">=3.14"` included Python 3.14.0/3.14.1, while current HA dependencies require at least 3.14.2. `uv` resolves all groups over the declared Python range, including the unselected `ha` group, so running Python 3.14.9 did not resolve that metadata contradiction.

The project now declares `>=3.14.2,<3.15`, pins development/CI to Python 3.14.9 and uv 0.13.5, and includes a universal `uv.lock`. Every installation job uses `uv sync --locked`. The in-process HA group also includes the frontend version required by its pinned HA fixture target; otherwise HA setup fails with `No module named 'hass_frontend'` after dependency installation succeeds.

A fresh Linux container, separate from the previously provisioned HA images, successfully resolved all groups, installed the locked `dev`/`container` environment, passed Ruff lint/format checks, and ran 66 passing tests with one explicit server-database skip. Five JavaScript tests also passed locally. This validates clean installation rather than relying on the earlier manually populated development environment.

A separate clean Linux installation of `dev`/`ha` then passed both in-process integration tests: 2 passed in 0.56 seconds on Python 3.14.9, HA 2026.10.4, `pytest-homeassistant-custom-component` 0.13.375 and frontend 20260930.5. The final lockfile contains 173 resolved packages across all groups. The GitHub-hosted workflow itself has not been rerun from this workspace.

Reproduction: `uv run python scripts/verify_ci_environment.py`, or add `--ha` for the in-process suite. Add `--update-lock` only when intentionally updating dependency metadata. The verifier uses an isolated Linux virtualenv and cache and does not replace the host development environment.
