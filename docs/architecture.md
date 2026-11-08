# repo-pulse architecture

repo-pulse is a Python command-line tool, built with Typer, that reports on GitHub repositories. All data comes from the `gh` CLI. No GitHub API token is handled directly.

## Modules

| Module | Responsibility |
|---|---|
| `cli.py` | Typer app. Parses arguments, wires the pieces together, sets exit codes. |
| `gh.py` | The only module that runs `gh`. Builds argument lists, runs the subprocess, parses JSON, and turns failures into `GhError`. |
| `models.py` | Dataclasses: `RepoSummary`, `PullRequest`, `Issue`, `Activity`. |
| `metrics.py` | Pure functions: ages, counts, activity rollups. No I/O. |
| `render.py` | Turns models into a `rich` table or JSON. |

## Flowchart

```mermaid
flowchart TD
    User([User]) -->|repo-pulse CMD OWNER/REPO| CLI

    subgraph repo_pulse [repo_pulse package]
        CLI[cli.py<br/>Typer app]
        GH[gh.py<br/>run_gh runner]
        Models[models.py<br/>dataclasses]
        Metrics[metrics.py<br/>pure logic]
        Render[render.py<br/>table / JSON]
    end

    CLI -->|summary| GH
    CLI -->|prs| GH
    CLI -->|issues| GH
    CLI -->|activity| GH

    GH -->|subprocess.run list args, no shell| GhCLI[[gh CLI]]
    GhCLI -->|HTTPS| GitHub[(GitHub API)]
    GhCLI -->|stdout JSON / stderr + exit code| GH

    GH -->|parsed dicts| Models
    GH -.->|GhError: not installed,<br/>not logged in, repo not found,<br/>non-zero exit| CLI
    Models --> Metrics
    Metrics --> Render
    Models --> Render
    Render -->|--json?| Choice{output format}
    Choice -->|default| Table[rich table on stdout]
    Choice -->|--json| JSON[raw JSON on stdout]
    CLI -.->|error message on stderr,<br/>exit code 1| User

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
    participant GH as gh.py
    participant Proc as gh CLI (subprocess)
    participant API as GitHub API
    participant Models as models.py
    participant Metrics as metrics.py
    participant Render as render.py

    User->>CLI: repo-pulse prs owner/repo
    CLI->>CLI: parse args (state=open, limit=20, json=False)
    CLI->>GH: list_prs("owner/repo", state="open", limit=20)
    GH->>Proc: gh pr list --repo owner/repo --state open --limit 20<br/>--json number,title,author,createdAt,reviewDecision,url
    Proc->>API: GraphQL query (gh's stored auth)
    API-->>Proc: PR data

    alt gh succeeded (exit 0)
        Proc-->>GH: stdout: JSON array
        GH->>GH: json.loads(stdout)
        GH->>Models: PullRequest.from_gh(item) for each item
        Models-->>GH: list[PullRequest]
        GH-->>CLI: list[PullRequest]
        CLI->>Metrics: add ages (now - createdAt)
        Metrics-->>CLI: rows with age
        CLI->>Render: render_prs(rows, as_json=False)
        Render-->>User: rich table on stdout
        CLI-->>User: exit code 0
    else gh missing, not logged in, or repo not found
        Proc-->>GH: stderr + non-zero exit (or FileNotFoundError)
        GH-->>CLI: raise GhError(message)
        CLI-->>User: one-line error on stderr, exit code 1
    end
```
