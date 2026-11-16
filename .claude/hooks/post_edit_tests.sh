#!/bin/bash
# PostToolUse hook for Edit|Write: run the test suite and show failures to Claude.
# The edit has already happened; exit 2 just feeds stderr back to Claude.
cd "$CLAUDE_PROJECT_DIR" || exit 0
[ -x .venv/bin/pytest ] || exit 0

output=$(.venv/bin/pytest -q 2>&1)
status=$?
if [ "$status" -ne 0 ]; then
  echo "Tests failed after this edit (pytest exit code $status):" >&2
  echo "$output" | tail -n 60 >&2
  exit 2
fi
exit 0
