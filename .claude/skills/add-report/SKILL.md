---
name: add-report
description: Use when adding a new report or subcommand to repo-pulse.
---

# Add a report to repo-pulse

Use the existing `prs` command as the template for every step: copy its shape rather than inventing a new one. Below, `<thing>` stands for the new report, e.g. `issues`.

Before starting, check you're not on `main` (CLAUDE.md: always work on a branch).

## 1. gh call in `src/repo_pulse/gh.py`

- Add a `<THING>_FIELDS` tuple next to `PR_FIELDS`, listing the `gh ... --json` fields you need.
- Add a `list_<thing>(repo, ..., runner=None)` function modeled on `list_prs`:
  - Build `args` as a list, adding `--repo` only when `repo` is given.
  - Call `run_gh(args, runner)`. Never call `subprocess` yourself, and never use `shell=True`.
  - Check the shape of the result (e.g. `isinstance(data, list)`). If it's wrong, raise `GhError` with a message that's safe to show the user.
  - Return a list of models built with `<Model>.from_gh(item)`.

## 2. Model in `src/repo_pulse/models.py`

- Add a `@dataclass(frozen=True)` with a `from_gh(cls, data)` classmethod, like `PullRequest`.
- Handle gh's edge cases in `from_gh`, not later: `author: null` becomes `"ghost"`, `""` becomes `None`, and ISO timestamps are parsed with `datetime.fromisoformat`.
- Any time-based logic goes in `src/repo_pulse/metrics.py` and takes `now` as an argument. Never read the system clock there.

## 3. Report module `src/repo_pulse/reports/<thing>.py`

Copy `reports/prs.py`. Then add it to `REPORTS` in `reports/__init__.py`; don't edit `cli.py`.

- At module level, define:
  - `<thing>_as_dicts(items, now)`: JSON-ready dicts with ISO-format dates; use `**age_fields(when, now)` from `render.py` for ages.
  - `<thing>_table(items, now, title)`: a `rich` `Table`; use `age_cell(when, now)` for the age column.
  - Any option types, e.g. a `--limit` `Annotated[...]`, named after the report (`PrLimitOpt`, `ReleaseLimitOpt`) because the help text differs per report. Reuse `RepoArg`, `SinceOpt` and `JsonOpt` from `reports/_common.py`; every report takes `--since`. Typer resolves annotations against module globals, so types defined inside `register()` won't work.
- `register(app, *, runner, clock)` defines `@app.command() def <thing>(...)`:
  - Start with `now = clock()` and `cutoff = since_cutoff(since, now)`. A bad `--since` becomes a usage error (exit 2) before gh runs.
  - Fetch with `fetch_or_exit(gh.list_<thing>, repo, ..., runner=runner)`. It handles the error contract (`error: <msg>` on stderr, exit 1). If gh can filter by date (as `gh pr list --search` can), pass the cutoff to `gh.list_<thing>`.
  - Always filter with `is_at_or_after(<item time>, cutoff)` from `metrics.py` as well, even when gh filtered too, because gh's date filters are coarser.
  - Output with `render_report(items, now, as_json=as_json, title=repo_title(repo, "...", since), noun="...", to_dicts=..., to_table=...)`. Never call `utc_now()` directly.

## 4. Tests (no network, ever)

- **Fixture:** save `tests/fixtures/<thing>_list.json` in real `gh --json` output format. Include the edge cases: a `null` author, an empty-string field, and items of different ages relative to `NOW` (`2026-01-15T12:00Z`).
- **`tests/conftest.py`:** add `<thing>_list_json` and `fake_gh_<thing>` fixtures, like `pr_list_json` and `fake_gh`.
- **`tests/test_gh.py`:**
  - Assert the exact argument list in `fake.calls`.
  - Assert that `--repo` is left out when `repo=None`.
  - Assert that the fixture parses.
  - Assert that bad output raises `GhError`.
- **`tests/test_models.py`:** test field mapping and each edge case in `from_gh`.
- **`tests/test_cli.py`:**
  - Use `invoke(fake, fixed_clock, "<thing>", ...)` to cover both the table output and `--json` output.
  - Cover the empty result.
  - Cover a gh failure, which should exit 1 with `error:` in the output.
  - Cover `--since`: older fixture items are dropped (and any gh-side filter argument is passed). Add `<thing>` to the `command` list in `test_invalid_since_is_a_usage_error_before_gh_runs`.
  - Use `FakeGh` and `fixed_clock`; never mock `subprocess`.
- **`tests/test_reports.py`:** add `<thing>` to the expected list of registered commands.
- Run `.venv/bin/pytest -q`. Everything must pass.

## 5. README report table

Add a row for the new report to the report table in `README.md`, with the command, what it shows, and its main options. If `README.md` or the table doesn't exist yet, create a `## Reports` table with a `prs` row as well, and tell the user you did.

## 6. `docs/architecture.md`

- If the new model isn't listed in the Modules table's `models.py` row, add it.
- Make sure the flowchart has a `Reports -->|<thing>| GH` edge.
- Add a `## Sequence: repo-pulse <thing> owner/repo` diagram modeled on the `prs` one, with a `reports/<thing>.py` participant between `cli.py` and `gh.py`, the real function names, and the exact `gh ... --json` argument list.
- If you renamed anything used in the `prs` sequence diagram, update that too.

## 7. Wrap up

- Update the list of existing commands in CLAUDE.md's "What this is" section.
- Commit with a `feat:` prefix after the tests pass. Don't push unless the user says "push".
