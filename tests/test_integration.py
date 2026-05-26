"""
Integration tests — scan_repos + config.exclude_dirs working end-to-end.

These tests exercise the full path from config loading → extra_skip
construction → scan_repos, simulating what main.py/_scan_worker does.
"""

import tempfile
from pathlib import Path

import pytest

from gitpulse import config as cfg_mod
from gitpulse.scanner import scan_repos


def _make_toml(content: str) -> Path:
    f = tempfile.NamedTemporaryFile(suffix=".toml", mode="w", delete=False)
    f.write(content)
    f.close()
    return Path(f.name)


class TestConfigToScannerIntegration:
    def test_exclude_dirs_from_config_prevents_scan(self, tmp_path):
        skip_dir = tmp_path / "Archive"
        skip_dir.mkdir()
        (skip_dir / ".git").mkdir()

        toml = _make_toml('[scan]\nexclude_dirs = ["Archive"]\n')
        cfg = cfg_mod.load(toml)

        extra_skip = set(cfg.scan.exclude_dirs) if cfg.scan.exclude_dirs else None
        result = scan_repos(tmp_path, extra_skip=extra_skip)
        assert skip_dir not in result

    def test_exclude_dirs_from_config_allows_other_repos(self, tmp_path):
        skip_dir = tmp_path / "Archive"
        skip_dir.mkdir()
        (skip_dir / ".git").mkdir()

        keep_dir = tmp_path / "myproject"
        keep_dir.mkdir()
        (keep_dir / ".git").mkdir()

        toml = _make_toml('[scan]\nexclude_dirs = ["Archive"]\n')
        cfg = cfg_mod.load(toml)

        extra_skip = set(cfg.scan.exclude_dirs) if cfg.scan.exclude_dirs else None
        result = scan_repos(tmp_path, extra_skip=extra_skip)
        assert keep_dir in result
        assert skip_dir not in result

    def test_empty_exclude_dirs_config_finds_all_repos(self, tmp_path):
        for name in ("a", "b", "c"):
            d = tmp_path / name
            d.mkdir()
            (d / ".git").mkdir()

        toml = _make_toml('[scan]\nexclude_dirs = []\n')
        cfg = cfg_mod.load(toml)

        extra_skip = set(cfg.scan.exclude_dirs) if cfg.scan.exclude_dirs else None
        result = scan_repos(tmp_path, extra_skip=extra_skip)
        assert len(result) == 3

    def test_no_config_file_finds_repos(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / ".git").mkdir()

        cfg = cfg_mod.load(tmp_path / "nonexistent.toml")
        extra_skip = set(cfg.scan.exclude_dirs) if cfg.scan.exclude_dirs else None
        result = scan_repos(tmp_path, extra_skip=extra_skip)
        assert repo in result

    def test_exclude_dirs_set_conversion_is_correct(self):
        toml = _make_toml('[scan]\nexclude_dirs = ["A", "B", "C"]\n')
        cfg = cfg_mod.load(toml)
        extra_skip = set(cfg.scan.exclude_dirs) if cfg.scan.exclude_dirs else None
        assert extra_skip == {"A", "B", "C"}

    def test_multiple_exclusions_all_applied(self, tmp_path):
        for name in ("Archive", "Backups", "OldWork"):
            d = tmp_path / name
            d.mkdir()
            (d / ".git").mkdir()

        keeper = tmp_path / "active"
        keeper.mkdir()
        (keeper / ".git").mkdir()

        toml = _make_toml('[scan]\nexclude_dirs = ["Archive", "Backups", "OldWork"]\n')
        cfg = cfg_mod.load(toml)

        extra_skip = set(cfg.scan.exclude_dirs) if cfg.scan.exclude_dirs else None
        result = scan_repos(tmp_path, extra_skip=extra_skip)
        assert result == [keeper]
