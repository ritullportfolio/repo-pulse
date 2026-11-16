#!/bin/bash
# Stop hook: macOS notification when Claude finishes responding.
osascript -e 'display notification "Claude is done" with title "Claude Code"' >/dev/null 2>&1
# Always exit 0: a Stop hook that exits 2 would stop Claude from finishing.
exit 0
