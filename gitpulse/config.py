"""
config.py — TOML configuration loader for GitPulse.

Reads ~/.config/gitpulse/config.toml (or a path supplied via --config).
Uses tomllib (stdlib, Python 3.11+) or tomli (backport, 3.10).
Missing file → silent fallback to built-in defaults.
CLI flags always take precedence over config values.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path

# tomllib is stdlib on 3.11+; tomli is the backport for 3.10
if sys.version_info >= (3, 11):
    import tomllib
else:
    try:
        import tomli as tomllib  # type: ignore[no-redef]
    except ImportError:
        tomllib = None  # type: ignore[assignment]

DEFAULT_CONFIG_PATH = Path("~/.config/gitpulse/config.toml")
EXAMPLE_CONFIG_PATH = Path("~/.config/gitpulse/config.toml.example")

_EXAMPLE_CONTENT = """\
# GitPulse configuration — copy to config.toml and edit as needed.

[scan]
# roots = ["~/projects", "~/work"]   # override --root; list of directories to scan

[author]
# emails = ["you@example.com"]       # used by digest mode; defaults to git config user.email

[watch]
enabled = true
interval_seconds = 5

[stale]
weeks = 8
default_branches = ["main", "master", "develop", "trunk"]

[bulk]
max_workers = 8

[digest]
default_window = "1d"
"""


@dataclass
class ScanConfig:
    roots: list[str] = field(default_factory=list)


@dataclass
class AuthorConfig:
    emails: list[str] = field(default_factory=list)


@dataclass
class WatchConfig:
    enabled: bool = True
    interval_seconds: int = 5


@dataclass
class StaleConfig:
    weeks: int = 8
    default_branches: list[str] = field(
        default_factory=lambda: ["main", "master", "develop", "trunk"]
    )


@dataclass
class BulkConfig:
    max_workers: int = 8


@dataclass
class DigestConfig:
    default_window: str = "1d"


@dataclass
class GitPulseConfig:
    scan: ScanConfig = field(default_factory=ScanConfig)
    author: AuthorConfig = field(default_factory=AuthorConfig)
    watch: WatchConfig = field(default_factory=WatchConfig)
    stale: StaleConfig = field(default_factory=StaleConfig)
    bulk: BulkConfig = field(default_factory=BulkConfig)
    digest: DigestConfig = field(default_factory=DigestConfig)


def _write_example_if_missing() -> None:
    example = EXAMPLE_CONFIG_PATH.expanduser()
    if not example.exists():
        try:
            example.parent.mkdir(parents=True, exist_ok=True)
            example.write_text(_EXAMPLE_CONTENT)
        except Exception:
            pass


def load(path: Path | None = None) -> GitPulseConfig:
    """Load and return the GitPulse configuration.

    Falls back to defaults silently if the file is absent or tomli is
    unavailable. Writes a .example file on first run.
    """
    cfg = GitPulseConfig()
    _write_example_if_missing()

    config_path = (path or DEFAULT_CONFIG_PATH).expanduser()
    if not config_path.exists():
        return cfg

    if tomllib is None:
        # Python 3.10 without tomli installed — use defaults
        return cfg

    try:
        with open(config_path, "rb") as fh:
            raw = tomllib.load(fh)
    except Exception:
        return cfg

    if "scan" in raw:
        s = raw["scan"]
        cfg.scan.roots = s.get("roots", [])

    if "author" in raw:
        a = raw["author"]
        cfg.author.emails = a.get("emails", [])

    if "watch" in raw:
        w = raw["watch"]
        cfg.watch.enabled = bool(w.get("enabled", True))
        cfg.watch.interval_seconds = int(w.get("interval_seconds", 5))

    if "stale" in raw:
        st = raw["stale"]
        cfg.stale.weeks = int(st.get("weeks", 8))
        cfg.stale.default_branches = list(
            st.get("default_branches", ["main", "master", "develop", "trunk"])
        )

    if "bulk" in raw:
        cfg.bulk.max_workers = int(raw["bulk"].get("max_workers", 8))

    if "digest" in raw:
        cfg.digest.default_window = str(raw["digest"].get("default_window", "1d"))

    return cfg


# Module-level singleton — loaded once, reused everywhere.
# Call load() explicitly if you need a custom path.
_default: GitPulseConfig | None = None


def get() -> GitPulseConfig:
    """Return the cached default config (loaded once on first call)."""
    global _default
    if _default is None:
        _default = load()
    return _default
