# repo-pulse

Quick health reports for GitHub repositories, powered by the [`gh` CLI](https://cli.github.com).

## Setup

Requires Python 3.11+ and a logged-in `gh` (`gh auth login`).

```sh
python3 -m venv .venv && .venv/bin/pip install -e '.[dev]'
```

## Reports

Every report takes an optional `OWNER/REPO` (defaults to the current directory's repo) and `--json` for machine-readable output.

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
