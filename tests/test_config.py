from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from repo_pulse.cli import create_app
from repo_pulse.config import Config, ConfigError, default_config_path, load_config

runner = CliRunner()


def invoke(fake, clock, *args: str, config: Config | None = None, env: dict | None = None):
    app = create_app(runner=fake, clock=clock, config_override=config)
    return runner.invoke(app, list(args), env=env)


TITLES = {"prs": "open pull requests", "releases": "latest releases"}


def repo_flag(fake) -> str:
    call = fake.calls[0]
    return call[call.index("--repo") + 1]


# --- load_config -----------------------------------------------------------


def test_missing_file_is_an_empty_config(tmp_path: Path) -> None:
    assert load_config(tmp_path / "nope.toml") == Config()


def test_load_default_repo(tmp_path: Path) -> None:
    path = tmp_path / "c.toml"
    path.write_text('default_repo = "cli/cli"\n')
    assert load_config(path) == Config(default_repo="cli/cli")


@pytest.mark.parametrize("body", ["default_repo = ", "default_repo = 3", 'default_repo = "nope"'])
def test_bad_config_raises(tmp_path: Path, body: str) -> None:
    path = tmp_path / "c.toml"
    path.write_text(body)
    with pytest.raises(ConfigError):
        load_config(path)


def test_default_path_respects_xdg(tmp_path: Path) -> None:
    assert default_config_path({"XDG_CONFIG_HOME": str(tmp_path)}) == (
        tmp_path / "repo-pulse" / "config.toml"
    )
    assert default_config_path({}).parts[-3:] == (".config", "repo-pulse", "config.toml")


# --- CLI -------------------------------------------------------------------


@pytest.mark.parametrize("cmd", ["prs", "releases"])
def test_no_config_file_uses_current_repo(cmd, fake_gh, fake_gh_releases, fixed_clock, tmp_path):
    fake = fake_gh if cmd == "prs" else fake_gh_releases
    result = invoke(fake, fixed_clock, "--config", str(tmp_path / "missing.toml"), cmd)
    assert result.exit_code == 0, result.output
    assert "--repo" not in fake.calls[0]
    assert f"current repo: {TITLES[cmd]}" in result.output


@pytest.mark.parametrize("cmd", ["prs", "releases"])
def test_config_default_repo_is_used(cmd, fake_gh, fake_gh_releases, fixed_clock, tmp_path):
    fake = fake_gh if cmd == "prs" else fake_gh_releases
    path = tmp_path / "c.toml"
    path.write_text('default_repo = "cli/cli"\n')
    result = invoke(fake, fixed_clock, "--config", str(path), cmd)
    assert result.exit_code == 0, result.output
    assert repo_flag(fake) == "cli/cli"
    assert f"cli/cli: {TITLES[cmd]}" in result.output


@pytest.mark.parametrize("cmd", ["prs", "releases"])
def test_cli_argument_overrides_config(cmd, fake_gh, fake_gh_releases, fixed_clock, tmp_path):
    fake = fake_gh if cmd == "prs" else fake_gh_releases
    path = tmp_path / "c.toml"
    path.write_text('default_repo = "cli/cli"\n')
    result = invoke(fake, fixed_clock, "--config", str(path), cmd, "acme/widgets")
    assert result.exit_code == 0, result.output
    assert repo_flag(fake) == "acme/widgets"


def test_injected_config(fake_gh, fixed_clock) -> None:
    result = invoke(fake_gh, fixed_clock, "prs", config=Config(default_repo="acme/widgets"))
    assert result.exit_code == 0, result.output
    assert repo_flag(fake_gh) == "acme/widgets"


def test_env_var_selects_config(fake_gh, fixed_clock, tmp_path) -> None:
    path = tmp_path / "c.toml"
    path.write_text('default_repo = "cli/cli"\n')
    result = invoke(fake_gh, fixed_clock, "prs", env={"REPO_PULSE_CONFIG": str(path)})
    assert result.exit_code == 0, result.output
    assert repo_flag(fake_gh) == "cli/cli"


@pytest.mark.parametrize("cmd", ["prs", "releases"])
def test_invalid_toml_is_a_clean_error(cmd, fake_gh, fixed_clock, tmp_path) -> None:
    path = tmp_path / "c.toml"
    path.write_text("default_repo = [oops\n")
    result = invoke(fake_gh, fixed_clock, "--config", str(path), cmd)
    assert result.exit_code == 1
    assert "error: invalid TOML" in result.output
    assert "Traceback" not in result.output
    assert fake_gh.calls == []


@pytest.mark.parametrize("cmd", ["prs", "releases"])
def test_explicit_repo_ignores_a_broken_config(cmd, fake_gh, fake_gh_releases, fixed_clock, tmp_path):
    # The file is only read when no OWNER/REPO is given, so a broken one can't block you.
    fake = fake_gh if cmd == "prs" else fake_gh_releases
    path = tmp_path / "c.toml"
    path.write_text("default_repo = [oops\n")
    result = invoke(fake, fixed_clock, "--config", str(path), cmd, "acme/widgets")
    assert result.exit_code == 0, result.output
    assert repo_flag(fake) == "acme/widgets"


def test_unreadable_config_is_a_clean_error(fake_gh, fixed_clock, tmp_path) -> None:
    path = tmp_path / "c.toml"
    path.write_bytes(b"\xff\xfe not utf-8")
    result = invoke(fake_gh, fixed_clock, "--config", str(path), "prs")
    assert result.exit_code == 1
    assert "error: cannot read config file" in result.output
    assert "Traceback" not in result.output
    assert fake_gh.calls == []


def test_config_path_that_is_a_directory_is_a_clean_error(fake_gh, fixed_clock, tmp_path) -> None:
    result = invoke(fake_gh, fixed_clock, "--config", str(tmp_path), "prs")
    assert result.exit_code == 1
    assert "error: cannot read config file" in result.output
    assert fake_gh.calls == []


def test_invalid_default_repo_is_a_clean_error(fake_gh, fixed_clock, tmp_path) -> None:
    path = tmp_path / "c.toml"
    path.write_text('default_repo = "just-a-name"\n')
    result = invoke(fake_gh, fixed_clock, "--config", str(path), "prs")
    assert result.exit_code == 1
    assert "error: invalid default_repo" in result.output
    assert fake_gh.calls == []


def test_xdg_config_home_is_used_end_to_end(fake_gh, fixed_clock, tmp_path, monkeypatch) -> None:
    xdg = tmp_path / "xdg"
    (xdg / "repo-pulse").mkdir(parents=True)
    (xdg / "repo-pulse" / "config.toml").write_text('default_repo = "cli/cli"\n')
    monkeypatch.setenv("XDG_CONFIG_HOME", str(xdg))
    result = invoke(fake_gh, fixed_clock, "prs")
    assert result.exit_code == 0, result.output
    assert repo_flag(fake_gh) == "cli/cli"


def test_config_option_beats_env_var(fake_gh, fixed_clock, tmp_path) -> None:
    from_env = tmp_path / "env.toml"
    from_env.write_text('default_repo = "env/repo"\n')
    from_flag = tmp_path / "flag.toml"
    from_flag.write_text('default_repo = "flag/repo"\n')
    result = invoke(
        fake_gh, fixed_clock, "--config", str(from_flag), "prs",
        env={"REPO_PULSE_CONFIG": str(from_env)},
    )
    assert result.exit_code == 0, result.output
    assert repo_flag(fake_gh) == "flag/repo"


def test_config_override_ignores_the_config_option(fake_gh, fixed_clock, tmp_path) -> None:
    path = tmp_path / "c.toml"
    path.write_text('default_repo = "file/repo"\n')
    result = invoke(
        fake_gh, fixed_clock, "--config", str(path), "prs", config=Config(default_repo="acme/widgets")
    )
    assert result.exit_code == 0, result.output
    assert repo_flag(fake_gh) == "acme/widgets"
