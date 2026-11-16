#!/usr/bin/env python3
"""PreToolUse hook for Bash: block commands that touch .env files, and pushes to main.

Exit 2 blocks the command; the message on stderr is shown to Claude.
"""
from __future__ import annotations

import json
import re
import shlex
import subprocess
import sys

# .env, .env.local, config.env, ./app/.env, but not .envrc, .environ or .venv
ENV_RE = re.compile(r"\.env(?![A-Za-z0-9])")
SEPARATORS = {";", "&&", "||", "|", "&", "\n"}
PROTECTED = {"main", "refs/heads/main"}


def block(msg: str) -> None:
    print(msg, file=sys.stderr)
    sys.exit(2)


def current_branch(cwd: str | None) -> str:
    result = subprocess.run(
        ["git", "branch", "--show-current"], cwd=cwd, capture_output=True, text=True
    )
    return result.stdout.strip()


def segments(cmd: str) -> list[list[str]]:
    """Split a shell command into simple commands, e.g. 'a && b; c' -> [[a], [b], [c]]."""
    lexer = shlex.shlex(cmd, posix=True, punctuation_chars=";&|")
    lexer.whitespace_split = True
    parts: list[list[str]] = [[]]
    for token in lexer:
        if token in SEPARATORS:
            parts.append([])
        else:
            parts[-1].append(token)
    return [p for p in parts if p]


def pushes_to_main(tokens: list[str], cwd: str | None) -> bool:
    if "git" not in tokens or "push" not in tokens:
        return False
    if tokens.index("push") < tokens.index("git"):
        return False
    args = tokens[tokens.index("push") + 1:]
    if "--all" in args or "--mirror" in args:
        return True  # these push main along with everything else
    positional = [a for a in args if not a.startswith("-")]
    refspecs = positional[1:]  # positional[0] is the remote
    if not refspecs:
        # Bare "git push" or "git push origin" pushes the current branch.
        return current_branch(cwd) == "main"
    for spec in refspecs:
        dst = spec.lstrip("+").split(":")[-1]
        if dst == "HEAD":
            dst = current_branch(cwd)
        if dst in PROTECTED:
            return True
    return False


def main() -> None:
    data = json.load(sys.stdin)
    cmd = data.get("tool_input", {}).get("command", "")
    cwd = data.get("cwd")

    if ENV_RE.search(cmd):
        block(
            "Blocked by .claude/hooks/pre_bash.py: this command mentions a .env file. "
            ".env files can hold secrets, so Claude must not read, search or print them. "
            "If you need a value from one, ask the user."
        )

    try:
        parsed = segments(cmd)
    except ValueError:
        # Unparseable (e.g. unbalanced quotes): err on the side of blocking.
        if re.search(r"\bgit\b.*\bpush\b.*\bmain\b", cmd):
            block("Blocked by .claude/hooks/pre_bash.py: could not parse this git push, and it mentions main.")
        return

    for tokens in parsed:
        if pushes_to_main(tokens, cwd):
            block(
                "Blocked by .claude/hooks/pre_bash.py: this git push targets main. "
                "CLAUDE.md says work on a branch, never directly on main. "
                "Push a feature branch and open a PR instead."
            )


if __name__ == "__main__":
    main()
