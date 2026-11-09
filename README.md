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
| `repo-pulse prs [OWNER/REPO]` | Recent pull requests with author, age and review status | `--state open\|closed\|merged\|all` (default `open`), `--limit` (default 20) |
| `repo-pulse releases [OWNER/REPO]` | Latest releases with tag, name, age and status (latest / pre-release / draft) | `--limit` (default 10) |

```sh
.venv/bin/repo-pulse releases cli/cli --limit 5
```
