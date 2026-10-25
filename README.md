# pax0r's Listkeeper

A local Home Assistant integration extending the native shopping list with approved aliases, safe deduplication, permanent purchase history and statistics. HA domain: `pax0r_listkeeper`. Maintainer: [pax0r](https://github.com/pax0r). Repository: [pax0r/listkeeper](https://github.com/pax0r/listkeeper).

## Features

- Event-driven reconciliation, including bulk Shopping List operations.
- Unicode NFC, case and whitespace normalization; no fuzzy matching or AI.
- A clearly identified new active item replaces older duplicates while retaining its UID.
- Purchase history independent of Recorder retention, with corrections within 60 minutes inclusive.
- Manual name merges, historical reassignment, splitting and moving names between products.
- An administrator panel: dashboard, catalog, history, diagnostics, JSON export and explicit deletion.
- Local assets, HA themes, English by default and Polish localization; no CDN, telemetry or cloud.

## Manual installation

1. Set up HA's built-in **Shopping list** integration.
2. Copy `custom_components/pax0r_listkeeper` to `/config/custom_components/pax0r_listkeeper`.
3. Restart HA. Open **Settings → Devices & services → Add integration → pax0r's Listkeeper**.
4. Select the native entity, usually `todo.shopping_list`. Leave the SQL URL empty for detection.
5. Open **pax0r's Listkeeper** in the sidebar as an administrator.

Basic setup requires no YAML. HA/HACS may download the Python requirements from `manifest.json` during installation; provision them beforehand for disconnected installations. The running integration requires no internet. Target: HA 2026.10+; actual compatibility results are recorded in [VALIDATION.md](docs/VALIDATION.md).

## HACS

After publishing the repository, add `https://github.com/pax0r/listkeeper` under **HACS → Custom repositories**, category **Integration**. Install, restart and configure as above. The repository contains `hacs.json` and the required directory layout; these do not automatically publish it in HACS's default catalog. HACS and hassfest jobs are included in CI.

## Database configuration

An isolated adapter attempts to discover Recorder's URL. Listkeeper creates independent SQLAlchemy engines and sessions. Missing configuration falls back to separate SQLite; manual server URLs are supported.

| Backend | Isolation | Required permissions |
| --- | --- | --- |
| SQLite | `/config/pax0r_listkeeper.db`, never Recorder's file | Configuration directory write access |
| PostgreSQL | Schema `pax0r_listkeeper` | Database CREATE, or USAGE/CREATE on a pre-created schema; owned-table DML |
| MySQL / MariaDB | Tables prefixed `pax0r_listkeeper_` | CREATE, INDEX, SELECT, INSERT, UPDATE, DELETE on owned tables |

Setup tests connectivity and applies Alembic migrations. SQL failures suspend deduplication; reconciliation retries after 30 seconds or the next list change. Healthy lists are not periodically polled.

Example manual URLs; enter your own credentials in the hidden configuration field:

```text
postgresql+psycopg2://USER:PASSWORD@HOST:5432/homeassistant
mysql+pymysql://USER:PASSWORD@HOST:3306/homeassistant?charset=utf8mb4
```

URL-encode password special characters. Credentials are stored in HA configuration: protect its files and backups. The panel never returns connection URLs or passwords. Every SQLite URL selects the integration's own fixed file.

Options change the list, deduplication, diagnostics and SQL. An empty SQL field preserves the current manual connection; reset restores detection. **Changing connections does not transfer history between databases.** Export and back up first. Only one integration instance is supported.

## History and deduplication rules

HA remains authoritative for the current list. Initial reconciliation creates a baseline; existing completed items do not create historical purchases. An observed active → completed transition records a purchase. Unchecking within 60 minutes inclusive cancels it logically with `quick_uncheck`; after that window, the purchase remains. Removing an item never deletes its history.

After restart, an unknown uncheck time never justifies cancellation. A known active item found completed after downtime is recorded as `recovery` with its detection time. Intermediate changes are not reconstructed. A newly discovered completed item has no observed transition and creates no purchase.

A clearly identified new active duplicate keeps its UID and replaces older active or completed items without deleting history. Unknown addition order prevents automatic deletion. Unlinked names remain different products. See [HA API review](docs/HA_API_REVIEW.md) for compatibility boundaries.

## Catalog and statistics

In **Products and names**, select names, choose the target and confirm the merge. This updates historical statistics and future matching. **Split** creates a separate product for a name; **Move** assigns it to an existing product. Decisions are logged without undoing subsequent changes. Original names and event IDs remain intact.

The catalog distinguishes occurrences (additions/renames) from confirmed purchase events. Normalization-only variants share a name record. The dashboard counts unique local purchase days per canonical product using HA's timezone. Two same-day events contribute one statistical purchase. Counts and dates respect all-history, 90-day and 30-day filters; frequency uses the full history and is labeled separately.

## Export, deletion and upgrades

Panel settings export JSON format version 1 containing catalog, snapshots, purchases and operation logs, without credentials. There is no automatic purge. Deletion requires typing `DELETE SHOPPING HISTORY`; the native list is unchanged. The next reconciliation creates a new baseline. Removing the integration entry preserves SQL data.

Before upgrading, back up SQLite while HA is stopped or take a consistent backup of the owned server schema/tables. Additive migrations `001 → 002` run during setup/startup. Downgrade requires restoring a backup. JSON import is outside the MVP.

## Development and tests

Use Python 3.14.2–3.14.x, Node.js 22+ and isolated databases. Development and CI pin Python 3.14.9 in `.python-version`, matching the HA container builds tested here. Never use production HA databases.

```powershell
uv sync --group dev --group container
uv run pytest
uv run ruff check custom_components tests scripts
uv run ruff format --check custom_components tests scripts
npm test
npm run check
```

`uv.lock` records all dependency groups. CI installs with `uv sync --locked`; after changing dependencies, run `uv lock` and commit the updated lockfile. `uv` resolves every group, including `ha`, even when it installs only `dev` and `container`. Therefore the declared Python range must satisfy HA's minimum of 3.14.2; simply selecting a newer interpreter in CI does not fix an incompatible project range.

The integration executes inside HA and uses HA's interpreter; do not install a separate Python runtime on HA OS for it. Host-side HTTP/WebSocket tests run outside HA and may use another compatible patch version. In-process HA tests must satisfy the installed HA package's Python requirement. To reproduce clean Linux dependency installation locally, run `uv run python scripts/verify_ci_environment.py`; add `--ha` for in-process HA tests.

For restricted temporary directories use `uv run pytest --basetemp .pytest-tmp`. `scripts/use_cached_dependencies.ps1` is an optional bootstrap for already cached packages.

In-process HA tests on Linux: `uv sync --group dev --group ha`, then `uv run pytest tests/ha`. The HA group pins the fixture package and the frontend release required by HA 2026.10.4; update this pair together when changing that test target. Server SQL tests require `SI_TEST_DATABASE_URL` pointing to an **empty isolated test database**. PostgreSQL, MySQL and MariaDB jobs are in `.github/workflows/tests.yml`.

Real HA process, API and restart tests:

```powershell
uv run python scripts/run_container_tests.py --project listkeeper-test-stable
uv run python scripts/run_container_tests.py --image ghcr.io/home-assistant/home-assistant:dev --project listkeeper-test-dev
```

`.github/workflows/ha-containers.yml` runs both channels and uploads JUnit, HA version, image ID and logs. Each run owns a configuration volume. See [container testing](docs/CONTAINER_TESTS.md) and [actual validation results](docs/VALIDATION.md).

The current code passed all 11 real-container scenarios on HA `2026.10.4` and `2026.11.0.dev202610250226` using SQLite. PostgreSQL/MySQL/MariaDB and browser rendering are separate checks and are not established by these runs.

## Limitations and roadmap

- Only native Shopping List is supported; ambiguous duplicates are preserved.
- Rapid edits and outages may conceal intermediate transitions; history records observed changes.
- Complete state is loaded per SQL transaction. Large archives need profiling and selective repositories.
- Next: verified HA/SQL compatibility, browser tests for light/dark/mobile layouts, selective queries, paginated export and history import.
- Later: additional deterministic matchers, median intervals and trends through the analytics port. Recommendations, fuzzy matching, AI, inventory, receipts and barcodes are outside this MVP.

See [architecture](docs/ARCHITECTURE.md) and [changelog](CHANGELOG.md).
