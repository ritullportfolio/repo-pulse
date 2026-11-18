"""One module per report. Each defines `register(app, *, runner, clock)`."""

from repo_pulse.reports import prs, releases

# Every report module, in --help order. Add new reports here.
REPORTS = [prs, releases]
