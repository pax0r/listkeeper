# Home Assistant container integration tests

## Test layers

- `tests/ha/`: in-process pytest using `pytest-homeassistant-custom-component`, covering the adapter, flow, WebSocket and unload. CI job: `homeassistant` in `.github/workflows/tests.yml`.
- `tests/containers/`: a real HA process in its official image, controlled over HTTP/WebSocket, with Docker Compose managing startup, restart and shutdown. CI matrix: `stable` / `dev` in `.github/workflows/ha-containers.yml`.

Images are published in the [official registry](https://github.com/home-assistant/core/pkgs/container/home-assistant). See HA's [WebSocket protocol](https://contributors.home-assistant.io/core/internals/websocket-api/). Pytest runs on the host and exercises the same authenticated APIs as the frontend.

## Local execution

Requirements: Docker Engine with Linux containers, Compose v2, Python 3.14+ and `uv`. Windows: use Docker Desktop with WSL2/Linux. Initial image and package downloads need network access.

```powershell
uv sync --group dev --group container
uv run python scripts/run_container_tests.py --project listkeeper-test-stable
uv run python scripts/run_container_tests.py --image ghcr.io/home-assistant/home-assistant:dev --project listkeeper-test-dev
```

Defaults: `stable` image, port `8124`. Change the port with `--port 8125`. Each run requires a fresh Compose project. The runner removes its containers and configuration volume afterward. `--keep` retains them for inspection; another run needs a new project name.

To remove a retained test project and its test history:

```powershell
docker compose -f compose.ha-test.yml -p listkeeper-test-dev down --volumes
```

The runner accepts only `listkeeper-test` or names starting with `listkeeper-test-`, refusing existing containers or volumes. Never reuse a production project's name.

After a forcefully interrupted run, `uv run python scripts/cleanup_test_stack.py listkeeper-test-dev` verifies test labels, saves logs and removes the owned stack. `scripts/inspect_test_runtime.py CONTAINER_NAME` prints non-secret native-list and SQL diagnostics only for explicitly marked test containers.

## Scenarios

1. Fresh owner onboarding, native Shopping List setup and Listkeeper Config Flow.
2. Exact/case/whitespace deduplication, preservation of the new UID, no false purchase.
3. Completion, quick-uncheck cancellation and a subsequent purchase cycle.
4. A new active duplicate replacing a completed item without losing history.
5. Historical name merge, alias deduplication, splitting and updated statistics.
6. Percentage-based product distinctions, rename and bulk completion.
7. Purchase event IDs surviving a real container restart, entry reload and item deletion.
8. Options Flow disabling and re-enabling deduplication.
9. Panel registration, local frontend modules, schema version and singleton enforcement.
10. Invalid deletion confirmation, unauthorized reads/mutations, anonymous requests and panel visibility for ordinary users.

Deduplication parameterization gives 11 cases. Controlled-time unit tests cover the 60/61-minute boundary and complex SQL failures; container tests do not wait an hour or modify HA's clock.

## Isolation and reproducibility

Compose owns a separate `/config` volume, Recorder SQLite file and `pax0r_listkeeper.db`. The integration is mounted read-only. No production configuration or Docker socket is mounted inside HA. HTTP binds only to `127.0.0.1`.

Fixtures inspect container labels and loopback port bindings rather than accepting arbitrary HA URLs/tokens. They reject configured volumes. Each scenario clears only its isolated native list and Listkeeper records. Passwords are random; credentials remain in memory and are excluded from reports.

Only user onboarding runs. Completing HA's `core_config` onboarding also creates network integrations, so tests intentionally skip it. Minimal configuration excludes `default_config` and cloud integrations.

The test image installs the integration manifest requirements while constraining SQLAlchemy to the selected image's Recorder version. A conflict fails the build instead of silently replacing HA's library.

Use a full tag or digest through `--image` for reproducible reruns. `stable` and `dev` are moving channels. Reports retain the actual HA version and derived image ID.

## GitHub Actions and reports

The container workflow runs for PRs, pushes to `main`/`master`, manual dispatch and Mondays at 05:23 UTC. Neither channel uses `continue-on-error`; separate jobs preserve both results. Jobs have a 35-minute timeout and clean up test resources afterward.

Artifacts `ha-stable-results` / `ha-dev-results`, retained for seven days, contain JUnit XML when pytest starts, `ha-version.json`, `image.json` and HA logs including startup failures. Raw `.storage`, databases and credentials are not uploaded. API failures report operation and code without authentication response bodies. Build output remains in Actions logs.

## Validation scope

Run client/runner mechanics with `uv run pytest tests/test_container_harness.py`. Full container tests run through the wrapper; ordinary pytest explicitly skips them. Requested container tests fail if Docker or HA is unavailable, rather than silently passing. See [actual validation results](VALIDATION.md).

The scenarios check panel registration and asset delivery, not browser rendering or interaction. In-process HA tests and SQL server tests remain separate verification layers.
