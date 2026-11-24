#!/usr/bin/env bash
# Generate CHANGELOG.md from git history using Claude Code in headless mode.
#
# Usage: scripts/changelog.sh [RANGE]
#   RANGE defaults to everything since the latest tag, or all history if there are no tags.
#   Examples: scripts/changelog.sh
#             scripts/changelog.sh v0.1.0..HEAD
set -euo pipefail

cd "$(git rev-parse --show-toplevel)"

if ! command -v claude >/dev/null 2>&1; then
  echo "error: the claude CLI was not found on PATH" >&2
  exit 1
fi

if [[ $# -gt 0 ]]; then
  range="$1"
elif last_tag="$(git describe --tags --abbrev=0 2>/dev/null)"; then
  range="${last_tag}..HEAD"
else
  range="HEAD"
fi

# One line per commit: short hash, date, subject. Merge commits are skipped
# because their subjects ("Merge pull request #8 ...") duplicate the real commits.
log="$(git log --no-merges --date=short --pretty=format:'%h %ad %s' "$range")"
if [[ -z "$log" ]]; then
  echo "error: no commits in range '$range'" >&2
  exit 1
fi

prompt='Turn the git log on stdin into a changelog in Markdown.

Rules:
- Start with exactly "# Changelog", then one blank line.
- Group commits under these headings, in this order, and omit empty groups:
  "## Features" (feat:), "## Fixes" (fix:), "## Documentation" (docs:),
  "## Tests" (test:), "## Chores" (chore:), "## Other" (anything else).
- One bullet per change: drop the prefix, start with a capital letter, keep it
  to one line, and end with the short hash in backticks, e.g. "- Add --since filter (`55ebf32`)".
- Keep issue or PR references like (#5) that appear in the subject.
- Merge near-duplicate commits into one bullet listing both hashes.
- Use only the commits given. Do not invent changes.
- Output only the Markdown, with no preamble and no code fences.'

tmp="$(mktemp)"
trap 'rm -f "$tmp"' EXIT

# Allowlist, not denylist: everything Claude needs comes in on stdin.
#   --tools ""            no built-in tools (Bash, Read, Edit, Write, WebFetch, WebSearch, ...)
#   --strict-mcp-config   only MCP servers from --mcp-config, and none are given
printf '%s\n' "$log" | claude -p "$prompt" --tools "" --strict-mcp-config > "$tmp"

# Only replace CHANGELOG.md if the output looks right.
if ! head -n 1 "$tmp" | grep -qx '# Changelog'; then
  echo "error: unexpected output from claude; CHANGELOG.md not changed. Output was:" >&2
  cat "$tmp" >&2
  exit 1
fi

chmod 644 "$tmp"  # mktemp creates files as 600
mv "$tmp" CHANGELOG.md
trap - EXIT
echo "wrote CHANGELOG.md ($(grep -c '^- ' CHANGELOG.md) entries from range '$range')"
