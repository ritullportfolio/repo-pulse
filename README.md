# repo-pulse

Quick health reports for GitHub repositories, powered by the [`gh` CLI](https://cli.github.com).

## Setup

Requires Python 3.11+ and a logged-in `gh` (`gh auth login`).

```sh
python3 -m venv .venv && .venv/bin/pip install -e '.[dev]'
```

## Config file

Optionally set a default repo so you don't have to type `OWNER/REPO`. It is a TOML file:

```toml
# ~/.config/repo-pulse/config.toml
default_repo = "cli/cli"
```

The repo comes from, highest priority first: the `OWNER/REPO` argument, `default_repo` from the config file, then the current directory's repo.

The file is looked up at `--config PATH`, then the `REPO_PULSE_CONFIG` environment variable, then `$XDG_CONFIG_HOME/repo-pulse/config.toml`, then `~/.config/repo-pulse/config.toml`. A missing file is fine. A file with invalid TOML (or a `default_repo` that isn't `OWNER/REPO`, or a path that can't be read) prints `error: ...` and exits 1; it is only read when no `OWNER/REPO` argument is given.

`--config` belongs to `repo-pulse` itself, so it goes before the report name:

```sh
.venv/bin/repo-pulse --config ~/work/repo-pulse.toml prs    # works
.venv/bin/repo-pulse prs --config ~/work/repo-pulse.toml    # fails: No such option: --config
```

## Reports

Every report takes an optional `OWNER/REPO` (defaults to the config file's `default_repo`, then the current directory's repo) and `--json` for machine-readable output.

| Command | Shows | Main options |
|---|---|---|
| `repo-pulse prs [OWNER/REPO]` | Recent pull requests with author, age and review status | `--state open\|closed\|merged\|all` (default `open`), `--limit` (default 20), `--since 7d\|2026-10-01` |
| `repo-pulse releases [OWNER/REPO]` | Latest releases with tag, name, age and status (latest / pre-release / draft) | `--limit` (default 10), `--since 7d\|2026-10-01` |

```sh
.venv/bin/repo-pulse releases cli/cli --limit 5
.venv/bin/repo-pulse prs cli/cli --since 7d
```

`--since` takes a duration (`30m`, `12h`, `7d`, `2w`, `1y`) or an ISO date or datetime. Dates and datetimes without a timezone are UTC: `2026-10-01` means midnight UTC. For local midnight, add an offset, e.g. `2026-10-01T00:00+05:30`.

- `prs` asks GitHub for PRs created on or after the cutoff's date, then trims to the exact time. Unless the cutoff is exactly midnight UTC (a plain date like `2026-10-01`), `--limit N` can return fewer than N PRs. Even `7d` counts back from the current time, not from midnight.
- `releases` filters the `--limit` latest releases, so raise `--limit` to look further back.
