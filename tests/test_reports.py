from __future__ import annotations

import io
import json
from datetime import timedelta

import pytest
import typer
from rich.console import Console
from rich.table import Table

from repo_pulse import gh
from repo_pulse.cli import create_app
from repo_pulse.render import age_cell, age_fields, render_report
from repo_pulse.reports import REPORTS
from repo_pulse.reports._common import fetch_or_exit, repo_title
from tests.conftest import NOW, FakeGh


def registered_command_names(app: typer.Typer) -> list[str]:
    return [cmd.name or cmd.callback.__name__ for cmd in app.registered_commands]


def test_create_app_registers_every_report_in_order(fake_gh, fixed_clock) -> None:
    app = create_app(runner=fake_gh, clock=fixed_clock)
    assert registered_command_names(app) == ["prs", "releases"]


def test_every_report_module_has_register() -> None:
    assert REPORTS, "REPORTS must not be empty"
    for module in REPORTS:
        assert callable(getattr(module, "register", None)), module.__name__


# --- shared formatting (render.py) ---------------------------------------------


def test_age_fields_and_cell_use_the_given_now() -> None:
    when = NOW - timedelta(days=3)
    assert age_fields(when, NOW) == {"age_seconds": 3 * 24 * 3600, "age": "3d"}
    assert age_cell(when, NOW) == "3d"


def _rows(items, now):
    return [{"value": item} for item in items]


def _table(items, now, title):
    table = Table(title=title, min_width=60)  # wide enough that rich doesn't wrap the title
    table.add_column("Value")
    for item in items:
        table.add_row(str(item))
    return table


def _render(items, *, as_json: bool) -> str:
    out = io.StringIO()
    render_report(
        items, NOW, as_json=as_json, title="acme/widgets: things", noun="things",
        to_dicts=_rows, to_table=_table, console=Console(file=out, width=100),
    )
    return out.getvalue()


def test_render_report_empty_says_nothing_found() -> None:
    assert _render([], as_json=False).strip() == "No things found (acme/widgets: things)."


def test_render_report_table(capsys) -> None:
    out = _render(["alpha", "beta"], as_json=False)
    assert "acme/widgets: things" in out
    assert "alpha" in out and "beta" in out
    assert capsys.readouterr().out == ""  # tables go through the console, not print


def test_render_report_json_uses_plain_print(capsys) -> None:
    console_out = _render(["alpha"], as_json=True)
    assert console_out == ""  # nothing through rich
    assert json.loads(capsys.readouterr().out) == [{"value": "alpha"}]


def test_render_report_json_empty_is_empty_list(capsys) -> None:
    _render([], as_json=True)
    assert json.loads(capsys.readouterr().out) == []


# --- shared command pieces (reports/_common.py) -------------------------------


def test_fetch_or_exit_returns_result(fake_gh) -> None:
    prs = fetch_or_exit(gh.list_prs, "acme/widgets", runner=fake_gh)
    assert [pr.number for pr in prs] == [42, 41, 40]


def test_fetch_or_exit_turns_gh_error_into_exit_1(capsys) -> None:
    fake = FakeGh(returncode=1, stderr="GraphQL: Could not resolve to a Repository with the name 'acme/nope'.")
    with pytest.raises(typer.Exit) as excinfo:
        fetch_or_exit(gh.list_releases, "acme/nope", runner=fake)
    assert excinfo.value.exit_code == 1
    assert capsys.readouterr().err.startswith("error: gh failed: GraphQL: Could not resolve")


def test_repo_title() -> None:
    assert repo_title("acme/widgets", "latest releases") == "acme/widgets: latest releases"
    assert repo_title(None, "open pull requests") == "current repo: open pull requests"
