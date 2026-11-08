# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Working rules

- Work on a branch, never directly on `main`.
- Run `.venv/bin/pytest -q` before every commit; never commit failing tests.
- Commit messages use conventional prefixes: `feat:`, `fix:`, `docs:`, `test:`, `chore:`.
- Never push unless the user explicitly says "push".
- Every new command needs tests using `FakeGh` and `fixed_clock`.

## What this is

`repo-pulse` is a Python (>=3.11) CLI built with Typer that reports on GitHub repositories. All GitHub data comes from shelling out to the `gh` CLI; there is no direct API client and no token handling. Only the `prs` command exists so far. `summary`, `issues` and `activity` are planned (see `docs/architecture.md`).

## Commands

There is no `uv`/`pipx`; use the plain venv in `.venv/`.

```sh
python3 -m venv .venv && .venv/bin/pip install -e '.[dev]'   # setup
.venv/bin/pytest -q                                          # all tests
.venv/bin/pytest tests/test_cli.py::test_prs_json_output     # single test
.venv/bin/pytest -k format_age                               # by keyword
.venv/bin/repo-pulse prs cli/cli --limit 5                   # run against a real repo
```

No linter or formatter is configured yet.

## Architecture

Request flow: `cli.py` → `gh.py` → `gh` subprocess → `models.py` → `metrics.py` / `render.py`. Mermaid diagrams of this live in `docs/architecture.md`. Keep the `prs` sequence diagram in sync if function or field names change.

- **`gh.py` is the only place that runs `gh`.** Everything goes through `run_gh(args, runner)`, which returns parsed JSON and converts every failure (missing binary, not logged in, non-zero exit, bad JSON) into `GhError` with a user-facing message. Commands must call `gh` via this function, never `subprocess` directly. Arguments are passed as a list (no `shell=True`).
- **Dependency injection, not mocking.** Define new commands inside `cli.create_app(runner=..., clock=...)`; the entry point `app = create_app()` uses the real `gh` and `utc_now`.
- **`metrics.py` never reads the system clock**; functions take `now` explicitly. Any time-based logic must accept `now` so tests stay date-independent.
- **CLI error contract:** commands catch `GhError`, print `error: <msg>` to stderr and `raise typer.Exit(1)`. No tracebacks reach the user.
- `--json` output is printed with plain `print`, not `rich`, so it stays machine-readable. Tables use `rich`.
- The `@app.callback()` in `create_app` exists to force subcommand mode; without it Typer would collapse a single-command app and `repo-pulse prs` would stop working.

## Tests

- Tests never hit the network. `tests/conftest.py` provides `FakeGh` (records `calls`, returns canned stdout/stderr/returncode, or raises), the `fake_gh` fixture (loaded from `tests/fixtures/pr_list.json`), and `fixed_clock` pinned to `NOW = 2026-01-15T12:00Z`.
- CLI tests invoke `create_app(runner=fake, clock=clock)` through `typer.testing.CliRunner` and assert on `result.output` (which includes stderr).
- Fixture JSON mirrors real `gh --json` output, including edge cases: `author: null` (deleted user → `"ghost"`) and `reviewDecision: ""` (→ `None`).
