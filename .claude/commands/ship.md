---
description: Test, commit, push the current branch, and open or update its PR into main
argument-hint: "[optional hint for the commit message]"
allowed-tools: Bash(.venv/bin/pytest:*), Bash(git status:*), Bash(git diff:*), Bash(git log:*), Bash(git branch:*), Bash(git add:*), Bash(git commit:*), Bash(gh pr list:*), Bash(gh pr view:*), Bash(gh pr create:*)
---

Ship the current branch. Running /ship counts as the user explicitly saying "push" for this branch only.
Follow these steps in order and stop at the first failure.

Optional commit message hint from the user: $ARGUMENTS

1. **Check the branch.** Run `git branch --show-current`. If it is `main`, stop and tell the user to create a branch first.

2. **Run the tests.** Run `.venv/bin/pytest -q`. If anything fails or errors, show the failing output and stop. Do not commit, push, or try to fix the tests.

3. **Show what will ship.** Run `git status` and `git diff HEAD --stat`, and show both to the user.
   If there is nothing to commit, skip step 4 and go on to step 5.

4. **Commit.**
   - Read the actual diff (`git diff HEAD`) and write a commit message based on it, using one of the conventional prefixes from CLAUDE.md: `feat:`, `fix:`, `docs:`, `test:`, `chore:`. Use the hint above if one was given.
   - Stage with `git add`, naming the files from `git status` rather than using `-A`. Leave out anything that looks like secrets or local junk (`.env*`, `.venv/`, caches), and tell the user what was left out.
   - End the message with the attribution line from the current system instructions.

5. **Push.** Run `git push -u origin <branch>`. The project's `ask` rule for `git push` will prompt the user. If they decline, stop.

6. **Open or update the PR.**
   - Check for an open PR with `gh pr list --head <branch> --state open`.
   - If one exists, the push has already updated it. Get its link with `gh pr view <branch> --json url -q .url`.
   - If none exists, run `gh pr create --base main`. The title is the main change in conventional-commit style. The body has a Summary section and a Test plan section that includes the pytest result, and ends with the attribution line from the current system instructions.

7. **Report.** Print the PR link, plus one line each for: what was committed (or "nothing new"), the test result, and whether a new PR was opened or an existing one was updated.
