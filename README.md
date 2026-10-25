# pax0r's Listkeeper

A local Home Assistant integration extending selected lists in HA's native To-do app with approved aliases, safe deduplication, permanent purchase history and statistics. HA domain: `pax0r_listkeeper`. Maintainer: [pax0r](https://github.com/pax0r). Repository: [pax0r/listkeeper](https://github.com/pax0r/listkeeper).

## Features

- Event-driven reconciliation, including bulk Shopping List operations.
- Opt-in management of Shopping List and Local To-do lists, with independent catalogs and history.
- Case, whitespace and accent-insensitive matching, including `Mydło` / `mydlo`; no fuzzy matching or AI.
- One list entry per product across active and completed items, with active entries taking priority.
- Purchase history independent of Recorder retention, with corrections within 60 minutes inclusive.
- Manual name merges, historical reassignment, splitting and moving names between products.
- An administrator panel: dashboard, catalog, history, diagnostics, JSON export and explicit deletion.
- Local assets, HA themes, English by default and Polish localization; no CDN, telemetry or cloud.

## Manual installation

1. Set up HA's built-in **Shopping list** or **Local To-do** integration and create your lists in HA.
2. Copy `custom_components/pax0r_listkeeper` to `/config/custom_components/pax0r_listkeeper`.
3. Restart HA. Open **Settings → Devices & services → Add integration → pax0r's Listkeeper**.
4. Select only the lists you want Listkeeper to manage. Leave the SQL URL empty for detection.
5. Open **pax0r's Listkeeper** in the sidebar as an administrator.

Basic setup requires no YAML. HA/HACS may download the Python requirements from `manifest.json` during installation; provision them beforehand for disconnected installations. The running integration requires no internet. Target: HA 2026.10+; actual compatibility results are recorded in [VALIDATION.md](docs/VALIDATION.md).

## HACS

After publishing the repository, add `https://github.com/pax0r/listkeeper` under **HACS → Custom repositories**, category **Integration**. Install, restart and configure as above. The repository contains `hacs.json` and the required directory layout; these do not automatically publish it in HACS's default catalog. HACS and hassfest jobs are included in CI.

For HACS publication checks, commit [LICENSE](LICENSE) to the default branch and set GitHub repository topics, for example `home-assistant`, `hacs` and `custom-integration`, using the gear next to **About** on the repository page. Topics are GitHub settings; adding text to `hacs.json` or README does not set them.

## Database configuration

An isolated adapter attempts to discover Recorder's URL. Listkeeper creates independent SQLAlchemy engines and sessions. Missing configuration falls back to separate SQLite; manual server URLs are supported.

SQLAlchemy is supplied by HA itself and is intentionally absent from the custom integration's manifest requirements. The standalone development project still declares it for database and domain tests.

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

Options change the selected lists, deduplication, diagnostics and SQL. An empty SQL field preserves the current manual connection; reset restores detection. **Changing connections does not transfer history between databases.** Export and back up first. One integration instance manages all opted-in lists.

## Independent lists and opt-in

Choose **Settings → Devices & services → pax0r's Listkeeper → Configure → Lists to manage**. Only selected lists receive listeners or automatic cleanup. Unselected lists are untouched. Clearing all selections pauses list management. Removing a selection retains its stored data; selecting that same entity again resumes processing and reconciles changes made while it was excluded.

Use **Current list** at the top of the panel to switch context. Catalogs, aliases, purchases, statistics, diagnostics, refresh, merges, moves, exports and deletion apply only to that list. Switching clears pending selections and dialogs. A test list can contain the same names as your home list without affecting it. Data is namespaced within the shared integration database; it is not stored in separate database files.

The supported providers are **Shopping List** and **Local To-do**. Other lists visible in HA's To-do app are intentionally excluded until their update and UID-deletion behavior is verified. Local To-do tasks with different due dates or descriptions are preserved even when names match. No cloud-backed provider is required.

List ownership currently uses the entity ID. Changing the friendly name is safe; changing the entity ID creates a different context. Keep the original entity ID to resume existing data. Export each list before removing entities or changing their IDs.

## History and deduplication rules

HA remains authoritative for the current list. Initial reconciliation creates a baseline; existing completed items do not create historical purchases. An observed active → completed transition records a purchase. Unchecking within 60 minutes inclusive cancels it logically with `quick_uncheck`; after that window, the purchase remains. Removing an item never deletes its history.

After restart, an unknown uncheck time never justifies cancellation. A known active item found completed after downtime is recorded as `recovery` with its detection time. Intermediate changes are not reconstructed. A newly discovered completed item has no observed transition and creates no purchase.

A new active duplicate keeps its UID and replaces older active or completed entries without deleting history. Existing duplicates are also cleaned on startup, reload and refresh, including groups containing only completed items. An active entry always takes priority; within the same status, the latest observed entry survives, using observed addition order and finally UID to break ties. A baseline/offline observation does not establish the actual creation time. Every deletion revalidates identity and the complete list snapshot.

Matching ignores case, repeated whitespace and accents (including Polish `ł`), but preserves numbers, units and percentages. Existing accent variants are linked automatically during reconciliation; original name IDs, spellings and purchase events remain unchanged and the decision is logged. Other aliases require manual linking. See [HA API review](docs/HA_API_REVIEW.md) for compatibility boundaries.

In **Products and names**, expand **How to organize names** for instructions. Select two or more names and choose **Merge selected…**, then explicitly choose the main name in the confirmation dialog. Selection survives searching. Each row's **Actions** menu provides history, **Move to product…** with its own destination dialog, and **Separate**. Moving affects only the chosen name and its history; separation cannot override automatic accent-insensitive identity matching.

## Catalog and statistics

In **Products and names**, select names, choose the target and confirm the merge. This updates historical statistics and future matching. **Split** creates a separate product for a name; **Move** assigns it to an existing product. Decisions are logged without undoing subsequent changes. Original names and event IDs remain intact.

The catalog distinguishes occurrences (additions/renames) from confirmed purchase events. Normalization-only variants share a name record. The dashboard counts unique local purchase days per canonical product using HA's timezone. Two same-day events contribute one statistical purchase. Counts and dates respect all-history, 90-day and 30-day filters; frequency uses the full history and is labeled separately.

## Export, deletion and upgrades

Panel settings export JSON format version 1 containing the selected list's catalog, snapshots, purchases and operation logs, its `entity_id`, and no credentials. There is no automatic purge. Deletion requires typing `DELETE SHOPPING HISTORY` and affects only that context; HA list content is unchanged. The next reconciliation creates a new baseline. Removing the integration entry preserves SQL data.

Before upgrading, back up SQLite while HA is stopped or take a consistent backup of the owned server schema/tables. Additive migrations `001 → 002 → 003` run during setup/startup. Config entries migrate from version 1 to 2, retaining the previously selected list. The original catalog and purchase IDs remain associated with that context. If older releases were switched between lists, their formerly shared historical catalog remains together in the previously configured context; snapshots from other lists receive independent future catalog records. No historical events are deleted. Downgrade requires restoring a backup. JSON import is outside the MVP.

## Development and tests

Use Python 3.14.2–3.14.x, Node.js 22+ and isolated databases. Development and CI pin Python 3.14.9 in `.python-version`, matching the HA container builds tested here. Never use production HA databases.

```powershell
uv sync --group dev --group container
uv run pre-commit install
uv run pytest
npm test
```

`uv.lock` records all dependency groups. CI installs with `uv sync --locked`; after changing dependencies, run `uv lock` and commit the updated lockfile. `uv` resolves every group, including `ha`, even when it installs only `dev` and `container`. Therefore the declared Python range must satisfy HA's minimum of 3.14.2; simply selecting a newer interpreter in CI does not fix an incompatible project range.

Run `uv run pre-commit install` once per clone to activate the commit hook. Hooks run Ruff fixes and formatting, validate JSON/YAML/TOML, detect merge markers and normalize trailing whitespace/end-of-file newlines on staged files. If a hook fixes a file, review and stage the change, then retry the commit. Hook environments download tools on first use. CI runs `uv run pre-commit run --all-files --show-diff-on-failure` as a backstop. Routine agent work leaves lint/format checks to hooks and CI; behavioral tests remain separate.

The integration executes inside HA and uses HA's interpreter; do not install a separate Python runtime on HA OS for it. Host-side HTTP/WebSocket tests run outside HA and may use another compatible patch version. In-process HA tests must satisfy the installed HA package's Python requirement.

For restricted temporary directories use `uv run pytest --basetemp .pytest-tmp`. Resource parsing and domain-boundary checks run as ordinary pytest tests in `tests/test_repository.py`. Official hassfest validation runs directly in GitHub Actions.

In-process HA tests on Linux: `uv sync --group dev --group ha`, then `uv run pytest tests/ha`. The HA group pins the fixture package and the frontend release required by HA 2026.10.4; update this pair together when changing that test target. Server SQL tests require `SI_TEST_DATABASE_URL` pointing to an **empty isolated test database**. PostgreSQL, MySQL and MariaDB jobs are in `.github/workflows/tests.yml`.

Real HA process, API and restart tests:

```powershell
uv run python -m tests.containers.run --project listkeeper-test-stable
uv run python -m tests.containers.run --image ghcr.io/home-assistant/home-assistant:dev --project listkeeper-test-dev
```

`.github/workflows/ha-containers.yml` runs both channels and uploads JUnit, HA version, image ID and logs. Each run owns a configuration volume. See [container testing](docs/CONTAINER_TESTS.md) and [actual validation results](docs/VALIDATION.md).

The independent-list implementation passed 16 real-container scenarios on HA `2026.10.4` using SQLite, including multiple Local To-do lists and opt-in changes. Earlier releases also ran on development HA; see the validation record for exact scope. Server databases, development HA and browser rendering require their own checks.

## Limitations and roadmap

- Only Shopping List and Local To-do are verified; richer tasks with conflicting dates or descriptions are preserved.
- Rapid edits and outages may conceal intermediate transitions; history records observed changes.
- Complete state is loaded per SQL transaction. Large archives need profiling and selective repositories.
- Next: verified HA/SQL compatibility, browser tests for light/dark/mobile layouts, selective queries, paginated export and history import.
- Later: additional deterministic matchers, median intervals and trends through the analytics port. Recommendations, fuzzy matching, AI, inventory, receipts and barcodes are outside this MVP.

See [architecture](docs/ARCHITECTURE.md) and [changelog](CHANGELOG.md).

## License

This repository is distributed under the [MIT License](LICENSE). Third-party dependencies retain their own licenses.
