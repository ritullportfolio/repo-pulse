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

## 3. Render functions in `src/repo_pulse/render.py`

Mirror the three `prs` functions:
- `<thing>_as_dicts(items, now)` returns JSON-ready dicts with ISO-format dates.
- `<thing>_table(items, now, title)` returns a `rich` `Table`.
- `render_<thing>(items, now, *, as_json, title, console=None)`:
  - For `--json`, use plain `print(json.dumps(...))`, never `rich`.
  - If the result is empty, print a "No ... found (title)." line.
  - Otherwise print the table.

## 4. Command inside `create_app` in `src/repo_pulse/cli.py`

- Define `@app.command() def <thing>(...)` inside `create_app` so it receives the injected `runner` and `clock`.
- Take the same `repo` argument and the same `--limit` and `--json` options as `prs`.
- Follow the error contract: wrap the `gh.list_<thing>` call in `except gh.GhError as exc:`, then `typer.echo(f"error: {exc}", err=True)` and `raise typer.Exit(code=1) from None`.
- Pass `clock()` to the render function. Never call `utc_now()` directly.

## 5. Tests (no network, ever)

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
  - Use `FakeGh` and `fixed_clock`; never mock `subprocess`.
- Run `.venv/bin/pytest -q`. Everything must pass.

## 6. README report table

Add a row for the new report to the report table in `README.md`, with the command, what it shows, and its main options. If `README.md` or the table doesn't exist yet, create a `## Reports` table with a `prs` row as well, and tell the user you did.

## 7. `docs/architecture.md`

- If the new model isn't listed in the Modules table's `models.py` row, add it.
- Make sure the flowchart has a `CLI -->|<thing>| GH` edge.
- Add a `## Sequence: repo-pulse <thing> owner/repo` diagram modeled on the `prs` one, with the real function names and the exact `gh ... --json` argument list.
- If you renamed anything used in the `prs` sequence diagram, update that too.

## 8. Wrap up

- Update CLAUDE.md's line "Only the `prs` command exists so far" if it's no longer true.
- Commit with a `feat:` prefix after the tests pass. Don't push unless the user says "push".
