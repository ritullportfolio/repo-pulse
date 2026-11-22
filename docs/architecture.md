# repo-pulse architecture

repo-pulse is a Python command-line tool, built with Typer, that reports on GitHub repositories. All data comes from the `gh` CLI. No GitHub API token is handled directly.

## Modules

| Module | Responsibility |
|---|---|
| `cli.py` | Typer app: `--version`, the subcommand callback, and a loop that registers every module in `REPORTS`. No report code. |
| `reports/<name>.py` | One module per report (`prs.py`, `releases.py`). Each has a `register(app, *, runner, clock)` that defines its command, plus that report's JSON rows and table columns. |
| `reports/__init__.py` | `REPORTS = [prs, releases]`: the list of report modules, in `--help` order. |
| `reports/_common.py` | Shared command pieces: `RepoArg`, `JsonOpt`, `SinceOpt`, `since_cutoff` (bad `--since` → usage error, exit 2), `fetch_or_exit` (the `GhError` → `error:` / exit 1 contract), `repo_title`. |
| `gh.py` | The only module that runs `gh`. Builds argument lists, runs the subprocess, parses JSON, and turns failures into `GhError`. |
| `models.py` | Dataclasses: `RepoSummary`, `PullRequest`, `Release`, `Issue`, `Activity`. |
| `metrics.py` | Pure functions: ages, `--since` parsing (`parse_since`, `is_since`), counts, activity rollups. No I/O. |
| `render.py` | Shared output for every report: `render_report` (JSON / "No … found" / `rich` table), `age_fields`, `age_cell`. |

## Flowchart

```mermaid
flowchart TD
    User([User]) -->|repo-pulse CMD OWNER/REPO| CLI

    subgraph repo_pulse [repo_pulse package]
        CLI[cli.py<br/>Typer app]
        Reports[reports/*.py<br/>one module per report]
        Common[reports/_common.py<br/>RepoArg, JsonOpt, SinceOpt, fetch_or_exit]
        GH[gh.py<br/>run_gh runner]
        Models[models.py<br/>dataclasses]
        Metrics[metrics.py<br/>pure logic]
        Render[render.py<br/>render_report: table / JSON]
    end

    CLI -->|register each module in REPORTS| Reports
    Reports -.->|uses| Common

    Reports -->|summary| GH
    Reports -->|prs| GH
    Reports -->|releases| GH
    Reports -->|issues| GH
    Reports -->|activity| GH

    GH -->|subprocess.run list args, no shell| GhCLI[[gh CLI]]
    GhCLI -->|HTTPS| GitHub[(GitHub API)]
    GhCLI -->|stdout JSON / stderr + exit code| GH

    GH -->|parsed dicts| Models
    GH -.->|GhError: not installed,<br/>not logged in, repo not found,<br/>non-zero exit| Reports
    Models --> Reports
    Reports -->|items + to_dicts / to_table| Render
    Render --> Metrics
    Render -->|--json?| Choice{output format}
    Choice -->|default| Table[rich table on stdout]
    Choice -->|--json| JSON[raw JSON on stdout]
    Reports -.->|fetch_or_exit: error message on stderr,<br/>exit code 1| User

    subgraph tests [tests/]
        Fake[conftest.py<br/>fake gh runner]
        Fixtures[(fixtures/*.json)]
    end
    Fixtures --> Fake
    Fake -.->|injected in place of real gh| GH
```

## Sequence: `repo-pulse prs owner/repo`

```mermaid
sequenceDiagram
    autonumber
    actor User
    participant CLI as cli.py (Typer)
    participant Report as reports/prs.py
    participant GH as gh.py
    participant Proc as gh CLI (subprocess)
    participant API as GitHub API
    participant Models as models.py
    participant Metrics as metrics.py
    participant Render as render.py

    User->>CLI: repo-pulse prs owner/repo
    CLI->>CLI: parse args (state=open, limit=20, since=None, json=False)
    CLI->>Report: prs(...) (registered from REPORTS)
    Report->>Report: now = clock()
    opt --since given (e.g. 7d)
        Report->>Metrics: parse_since(since, now)<br/>via since_cutoff (reports/_common.py)
        Metrics-->>Report: cutoff datetime (bad value → usage error, exit 2, gh never runs)
    end
    Report->>GH: list_prs("owner/repo", state="open", limit=20, since=cutoff)<br/>via fetch_or_exit (reports/_common.py)
    GH->>Proc: gh pr list --repo owner/repo --state open --limit 20<br/>--json number,title,author,createdAt,reviewDecision,url
    opt since given
        Note over GH,Proc: + --search "created:>=YYYY-MM-DD" (cutoff's UTC date)
    end
    Proc->>API: GraphQL query (gh's stored auth)
    API-->>Proc: PR data

    alt gh succeeded (exit 0)
        Proc-->>GH: stdout: JSON array
        GH->>GH: json.loads(stdout)
        GH->>Models: PullRequest.from_gh(item) for each item
        Models-->>GH: list[PullRequest]
        GH-->>Report: list[PullRequest]
        opt since given
            Report->>Metrics: is_since(created_at, cutoff) for each PR<br/>(search is by date, so trim to the exact time)
        end
        Report->>Render: render_report(pull_requests, now, as_json=False,<br/>to_dicts=prs_as_dicts, to_table=prs_table)
        Render->>Metrics: age(created_at, now)
        Metrics-->>Render: timedelta
        Render-->>User: rich table on stdout
        CLI-->>User: exit code 0
    else gh missing, not logged in, or repo not found
        Proc-->>GH: stderr + non-zero exit (or FileNotFoundError)
        GH-->>Report: raise GhError(message)
        Report-->>User: fetch_or_exit: one-line error on stderr, exit code 1
    end
```

## Sequence: `repo-pulse releases owner/repo`

```mermaid
sequenceDiagram
    autonumber
    actor User
    participant CLI as cli.py (Typer)
    participant Report as reports/releases.py
    participant GH as gh.py
    participant Proc as gh CLI (subprocess)
    participant API as GitHub API
    participant Models as models.py
    participant Metrics as metrics.py
    participant Render as render.py

    User->>CLI: repo-pulse releases owner/repo
    CLI->>CLI: parse args (limit=10, since=None, json=False)
    CLI->>Report: releases(...) (registered from REPORTS)
    Report->>Report: now = clock()
    opt --since given (e.g. 2026-10-01)
        Report->>Metrics: parse_since(since, now)<br/>via since_cutoff (reports/_common.py)
        Metrics-->>Report: cutoff datetime (bad value → usage error, exit 2, gh never runs)
    end
    Report->>GH: list_releases("owner/repo", limit=10)<br/>via fetch_or_exit (reports/_common.py)
    GH->>Proc: gh release list --repo owner/repo --limit 10<br/>--json tagName,name,publishedAt,createdAt,isLatest,isPrerelease,isDraft
    Proc->>API: GraphQL query (gh's stored auth)
    API-->>Proc: release data, newest first

    alt gh succeeded (exit 0)
        Proc-->>GH: stdout: JSON array
        GH->>GH: json.loads(stdout)
        GH->>Models: Release.from_gh(item) for each item<br/>(name "" → None, zero publishedAt → None)
        Models-->>GH: list[Release]
        GH-->>Report: list[Release]
        opt since given
            Report->>Metrics: is_since(released_at, cutoff) for each release<br/>(gh release list has no date filter)
        end
        Report->>Render: render_report(release_list, now, as_json=False,<br/>to_dicts=releases_as_dicts, to_table=releases_table)
        Render->>Metrics: age(released_at, now)<br/>(publishedAt, or createdAt for drafts)
        Metrics-->>Render: timedelta
        Render-->>User: rich table on stdout (status: latest / pre-release / draft)
        CLI-->>User: exit code 0
    else gh missing, not logged in, or repo not found
        Proc-->>GH: stderr + non-zero exit (or FileNotFoundError)
        GH-->>Report: raise GhError(message)
        Report-->>User: fetch_or_exit: one-line error on stderr, exit code 1
    end
```
