"""Optional TOML config file: currently just `default_repo`.

Where the repo comes from, highest priority first: the OWNER/REPO argument, then
`default_repo` here, then the current directory's repo (gh's own default).

The file is found via `--config PATH`, then `REPO_PULSE_CONFIG`, then
`$XDG_CONFIG_HOME/repo-pulse/config.toml`, then `~/.config/repo-pulse/config.toml`.
A missing file is fine; an unreadable or invalid one raises `ConfigError`.
"""

from __future__ import annotations

import os
import re
import tomllib
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

_REPO_RE = re.compile(r"^[^/\s]+/[^/\s]+$")


class ConfigError(Exception):
    """The config file exists but can't be used. The message is shown to the user."""


@dataclass(frozen=True)
class Config:
    default_repo: str | None = None


def default_config_path(env: Mapping[str, str] | None = None) -> Path:
    env = os.environ if env is None else env
    xdg = env.get("XDG_CONFIG_HOME")
    base = Path(xdg) if xdg else Path.home() / ".config"
    return base / "repo-pulse" / "config.toml"


def load_config(path: Path) -> Config:
    """Read `path`. A missing file gives an empty Config."""
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return Config()
    except (OSError, UnicodeDecodeError) as exc:
        raise ConfigError(f"cannot read config file {path}: {exc}") from None
    try:
        data = tomllib.loads(text)
    except tomllib.TOMLDecodeError as exc:
        raise ConfigError(f"invalid TOML in config file {path}: {exc}") from None

    default_repo = data.get("default_repo")
    if default_repo is not None and (
        not isinstance(default_repo, str) or not _REPO_RE.match(default_repo)
    ):
        raise ConfigError(
            f"invalid default_repo in config file {path}: expected a string like OWNER/REPO"
        )
    return Config(default_repo=default_repo)
