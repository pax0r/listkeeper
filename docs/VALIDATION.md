# Validation record

This file records checks actually executed, separately from prepared CI configuration.

## Previous local baseline

October 25, 2026; Windows, Python 3.14.0, SQLAlchemy 2.0.54, Alembic 1.20.0, pytest 8.4.2, Ruff 0.16.5, Node.js 22.22.3, aiohttp 3.14.4.

| Check | Recorded result |
| --- | --- |
| `python -m pytest -q --basetemp .pytest-tmp-containers-4` | 65 passed, 13 environment-dependent skips |
| Ruff lint and formatting | Passed |
| Resource parsing and domain-boundary checks | Passed; now included in `tests/test_repository.py` |
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
- HACS: job prepared; no local success claimed. Official hassfest validation is recorded below.
- Browser rendering, interactions, themes and mobile layout: not verified by API or helper tests.

The [API review](HA_API_REVIEW.md) records documentation/source inspection, which does not substitute for runtime verification. No GitHub/HACS publication has been performed from this workspace.

## CI dependency bootstrap correction

The reported GitHub run failed before executing tests: `requires-python = ">=3.14"` included Python 3.14.0/3.14.1, while current HA dependencies require at least 3.14.2. `uv` resolves all groups over the declared Python range, including the unselected `ha` group, so running Python 3.14.9 did not resolve that metadata contradiction.

The project now declares `>=3.14.2,<3.15`, pins development/CI to Python 3.14.9 and uv 0.13.5, and includes a universal `uv.lock`. Every installation job uses `uv sync --locked`. The in-process HA group also includes the frontend version required by its pinned HA fixture target; otherwise HA setup fails with `No module named 'hass_frontend'` after dependency installation succeeds.

A fresh Linux container, separate from the previously provisioned HA images, successfully resolved all groups, installed the locked `dev`/`container` environment, passed Ruff lint/format checks, and ran 66 passing tests with one explicit server-database skip. Five JavaScript tests also passed locally. This validates clean installation rather than relying on the earlier manually populated development environment.

A separate clean Linux installation of `dev`/`ha` then passed both in-process integration tests: 2 passed in 0.56 seconds on Python 3.14.9, HA 2026.10.4, `pytest-homeassistant-custom-component` 0.13.375 and frontend 20260930.5. The final lockfile contains 173 resolved packages across all groups. The GitHub-hosted workflow itself has not been rerun from this workspace.

The temporary verification wrapper has been removed. The corresponding CI commands remain `uv sync --locked --group dev --group container` and `uv sync --locked --group dev --group ha`, followed by their pytest jobs. Use `uv lock` only when intentionally updating dependency metadata.

## Official hassfest validation

Executed the official `ghcr.io/home-assistant/hassfest:latest` container, digest `sha256:e5828f7e305518506d8b4e8346411357d68358531b761bd118fe6a1631feff44`. Result: **1 integration, 0 invalid integrations**, with no configuration-schema warning. CI runs the official action directly; no local wrapper is required.

The manifest now places `domain` and `name` first and sorts the remaining keys alphabetically. SQLAlchemy remains a standalone development dependency but is no longer listed as a custom integration requirement because HA already supplies it. `CONFIG_SCHEMA` delegates to HA's `config_entry_only_config_schema` helper; the import is deferred so pure domain tests do not require HA.

The 66 available local Python tests passed after this change. A clean Linux `dev`/`ha` installation also passed both in-process HA tests in 0.55 seconds, including setup, WebSocket access and unload with the new schema declaration. Ruff lint/format and structure checks passed. The separately prepared HACS validator and GitHub-hosted workflow are not implied to have passed by the local hassfest result.

## Cleanup and HACS publication metadata

Removed one-off bootstrap, inspection, cleanup and validation wrappers. Repository resource checks now run in `tests/test_repository.py`; container orchestration lives in `tests/containers/run.py` and is invoked as `python -m tests.containers.run`. CI and documentation use those commands.

After cleanup, 69 local Python tests and 5 JavaScript tests passed. The moved container runner executed all 11 scenarios successfully on HA 2026.10.4 in 8.51 seconds, then removed its container and configuration volume.

Added the maintainer-approved MIT license. GitHub must receive that file on the default branch before its license API and HACS can recognize it. Repository topics must be set in GitHub's About settings; they cannot be provided by local manifest files. No authenticated GitHub management connection is available in this workspace, so topic changes and a full remote HACS rerun remain outstanding.

HACS's missing-category warning is optional. The current official hassfest image rejected the newer `productivity_information.shopping_groceries` taxonomy entry; the optional field remains absent to keep the manifest compatible rather than bypassing validation.

## Running HACS validation locally

The official action can run through Docker. It checks the published GitHub repository and its metadata, not uncommitted files in the working directory. Push file changes before using it to verify those changes. GitHub topics must be configured in the repository's **About → settings → Topics**, for example `home-assistant`, `hacs` and `custom-integration`.

Provide a GitHub token through the existing `INPUT_GITHUB_TOKEN` environment variable using your local credential tooling; do not put it in source files, command arguments or shared logs. The current image reads that variable even though its missing-token error misleadingly names `GITHUB_TOKEN`. No write permission is needed for repository validation; comments are disabled below.

Run from PowerShell:

```powershell
docker run --rm `
  -e INPUT_GITHUB_TOKEN `
  -e INPUT_CATEGORY=integration `
  -e INPUT_REPOSITORY=pax0r/listkeeper `
  -e REPOSITORY_REF=main `
  -e INPUT_IGNORE=brands `
  -e INPUT_COMMENT=false `
  ghcr.io/hacs/action:main
```

This keeps the same ignored check as CI; license and topics remain enabled. The action uses GitHub APIs and therefore requires network access, independently of the integration's entirely local operation. See the [official action documentation](https://hacs.xyz/docs/publish/action/).

Local execution on 2026-10-25 successfully downloaded and started image digest `sha256:187499a09c5d41f9f0d42ff80d203ed87b974c028290140913b61e005fb0aab2`, but stopped before validation because no GitHub token was available. No local HACS success is claimed. The maintainer's latest CI log confirms license validation passed and topics was the sole failing check.

## Catalog UX and existing duplicate cleanup

After changing survivor selection, accent matching and catalog dialogs, the ordinary local suite passed **81 Python tests**, with 17 explicit environment-dependent skips (15 container cases, the HA module and the external SQL server test). All **8 JavaScript tests**, JS syntax checking and Ruff lint/format checks passed. SQLite coverage includes linking pre-existing accent variants while retaining both name IDs and purchase events. Failure recovery includes a completed-only batch interrupted after external deletion and before SQL acknowledgement.

The first real HA run passed 14 cases and failed completed-only cleanup: the native adapter still rejected a completed survivor. The adapter now accepts completed-to-completed deletion while rejecting removal of an active task in favor of a completed survivor. The final complete run passed **15 cases in 13.05 seconds on HA 2026.10.4**, including accent matching, existing completed/active/mixed groups after reload and unchanged history. Reports are under `test-results/listkeeper-test-dedup-final/`; the runner removed its container, network and configuration volume afterward.

Frontend tests exercise explicit main-name selection, per-row move destinations, cancellation and selection persistence across filtering using injected DOM controls. Browser rendering, focus behavior, themes and mobile layout remain unverified. This change has not been rerun against development HA or server SQL engines.

## Independent opt-in lists and commit hooks

The latest ordinary suite passed **92 Python tests**, with 18 explicit skips (16 container cases, the in-process HA module and the external SQL server test). **11 JavaScript tests** passed. Coverage includes independent identical names/UIDs, scoped deletion and export, rejection of foreign name/product IDs, legacy catalog/config-entry migration, Local To-do locking and unpublished calendar edits, context switches and stale frontend responses.

Final full container runs passed all **16 cases** on each target:

| Target | HA version | Result | Reports |
| --- | --- | --- | --- |
| Stable | 2026.10.4 | 16 passed in 16.48 seconds | `test-results/listkeeper-test-context-stable/` |
| Development | 2026.11.0.dev202610250226 | 16 passed in 15.67 seconds | `test-results/listkeeper-test-context-dev/` |

Both runs include native Shopping List plus two Local To-do entities, opted-out duplicate preservation, context-specific history/catalog/export/deletion, completed-task rename notifications, re-enabling retained data and an empty opt-in selection. Both test stacks were removed afterward. An earlier run exposed a test-client issue: an unconfigured non-admin client sent an empty entity ID, triggering schema validation before authorization. The client now omits unknown context instead of sending an invalid identifier.

Official hassfest passed with **1 integration, 0 invalid integrations** after the multi-list/config-flow changes. The optional category field remains absent because of the validator compatibility issue recorded above. Browser rendering, server SQL engines and GitHub-hosted execution of the updated workflows have not been verified by these runs.

CI now pins Ubuntu 24.04 and uses Node 24 versions of checkout, setup-node, setup-uv and upload-artifact. `.pre-commit-config.yaml` pins Ruff and file validation hooks; CI invokes that same configuration. The dependency lock was regenerated with Python 3.14.9 and contains 182 packages. After the maintainer requested hook-owned linting, no manual linter suite was run. Hook configuration validation passed; the hook suite itself has not been executed here. Installing the local Git hook was blocked by sandbox permissions on `.git/hooks/pre-commit`; a developer must run `uv run pre-commit install` in their writable checkout.

## Grouped catalog, header sorting and canonical-name editing

The current ordinary suite passed **100 Python tests**, with 19 explicit environment-dependent skips. All **22 frontend tests** passed. New coverage checks grouping by product identity, complete alias membership during searches/selections, aggregate sorting in both directions, expansion/collapse, null last-seen dates for approved names, canonical rename conflicts, history preservation and rename isolation between lists. A SQL test verifies that whole-product merging includes aliases not present in the client's selection and preserves an edited destination label. Moving a main name selects a remaining source label and is covered separately by SQL tests.

The grouped-merge WebSocket contract passed all 16 container scenarios on HA 2026.10.4. After canonical renaming was added, the expanded suite passed **17 scenarios in 14.75 seconds**, including rename authorization/validation, stable original purchase identity, future corrected-spelling deduplication and `name_conflict` errors. Reports are under `test-results/listkeeper-test-rename-catalog/`. The runner removed its container, network and configuration volume afterward.

No manual lint/format run was performed for these changes. Browser rendering and interactions remain unverified by the injected-DOM frontend tests. This update has not been rerun on development HA or server SQL engines; earlier compatibility evidence remains scoped to the revisions described above.
