# Repository Guidelines

## Project Structure

The public name is **pax0r's Listkeeper**; its HA domain is `pax0r_listkeeper`. Installable code lives in `custom_components/pax0r_listkeeper/`: pure rules in `domain/`, use cases and ports in `application/`, SQLAlchemy and HA adapters in `infrastructure/`, WebSocket handlers in `api/`, and local Web Components in `frontend/`.

Tests live in `tests/`. `tests/ha/` requires Home Assistant on Linux; `tests/containers/` exercises real HA Docker instances. Architecture, compatibility and validation notes live in `docs/`.

## Language Policy

Always maintain this project's documentation in English, including README, architecture notes, changelogs, contributor guides and agent instructions. Write comments, docstrings, technical messages and new documentation in English. English is the default UI language. Other languages belong in explicit localization resources or intentional multilingual test fixtures. Update documentation when behavior or commands change.

## Development Commands

- `uv sync --group dev --group container`: install development and HTTP test dependencies.
- `uv run pytest`: run available tests; external environments are explicitly skipped.
- `uv run pytest --basetemp .pytest-tmp`: use workspace temporary files if needed.
- `uv run ruff check custom_components tests`: lint Python.
- `uv run ruff format --check custom_components tests`: check formatting.
- `npm test` and `npm run check`: test frontend helpers and check syntax.
- `uv run python -m tests.containers.run`: run isolated HA integration tests.

## Coding and Testing

Use Python 3.14.2–3.14.x; development and CI pin 3.14.9 in `.python-version`. Use four-space indentation, type annotations, `snake_case` functions/modules and `PascalCase` classes. Domain code must not import HA, SQLAlchemy or Alembic. Application code uses ports for transactions and list mutations. Keep blocking SQL outside HA's event loop.

Test mechanics with controlled fixtures or injected fakes. Check real inputs for parsing, schema and consistency; never freeze production wording, record counts or editorial content in assertions. Keep corpus evaluations separate from unit tests. Never change production data to satisfy tests or test against production HA databases.

## Contributions and Agent Instructions

Use concise imperative commit subjects. Describe behavior, relevant issues, validation, migration effects and limitations in PRs. Include screenshots for panel changes when available. Never report unexecuted checks as successful.

Keep commands and scripts readable; never encode or obscure executable code. Put longer operations in readable scripts and execute them by path. Protect SQL credentials and preserve purchase history unless deletion is explicitly requested. Exclude environments, editor settings, caches and test databases from contributions.
