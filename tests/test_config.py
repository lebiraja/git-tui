"""
Tests for gitpulse/config.py

Covers:
- ScanConfig.exclude_dirs defaults to empty list
- exclude_dirs parsed correctly from TOML
- exclude_dirs absent from [scan] section → empty list
- Existing config keys still work (roots, watch, stale, etc.)
- Missing config file → silent defaults
- Malformed TOML → silent defaults
- exclude_dirs config example line is present
"""

import tempfile
from pathlib import Path

import pytest

from gitpulse.config import (
    ScanConfig,
    GitPulseConfig,
    load,
    _EXAMPLE_CONTENT,
)


# ---------------------------------------------------------------------------
# ScanConfig dataclass
# ---------------------------------------------------------------------------

class TestScanConfigDefaults:
    def test_roots_defaults_to_empty_list(self):
        cfg = ScanConfig()
        assert cfg.roots == []

    def test_exclude_dirs_defaults_to_empty_list(self):
        cfg = ScanConfig()
        assert cfg.exclude_dirs == []

    def test_exclude_dirs_is_list_type(self):
        cfg = ScanConfig()
        assert isinstance(cfg.exclude_dirs, list)

    def test_instances_do_not_share_exclude_dirs(self):
        a = ScanConfig()
        b = ScanConfig()
        a.exclude_dirs.append("X")
        assert b.exclude_dirs == []


# ---------------------------------------------------------------------------
# load() — exclude_dirs parsing
# ---------------------------------------------------------------------------

class TestLoadExcludeDirs:
    def _write_toml(self, content: str) -> Path:
        f = tempfile.NamedTemporaryFile(suffix=".toml", mode="w", delete=False)
        f.write(content)
        f.close()
        return Path(f.name)

    def test_exclude_dirs_parsed_from_scan_section(self):
        p = self._write_toml('[scan]\nexclude_dirs = ["Google Drive", "Dropbox"]\n')
        cfg = load(p)
        assert cfg.scan.exclude_dirs == ["Google Drive", "Dropbox"]

    def test_exclude_dirs_absent_gives_empty_list(self):
        p = self._write_toml('[scan]\nroots = ["~/projects"]\n')
        cfg = load(p)
        assert cfg.scan.exclude_dirs == []

    def test_exclude_dirs_single_entry(self):
        p = self._write_toml('[scan]\nexclude_dirs = ["mnt"]\n')
        cfg = load(p)
        assert cfg.scan.exclude_dirs == ["mnt"]

    def test_exclude_dirs_empty_array(self):
        p = self._write_toml('[scan]\nexclude_dirs = []\n')
        cfg = load(p)
        assert cfg.scan.exclude_dirs == []

    def test_exclude_dirs_is_list_type_after_parse(self):
        p = self._write_toml('[scan]\nexclude_dirs = ["X"]\n')
        cfg = load(p)
        assert isinstance(cfg.scan.exclude_dirs, list)

    def test_no_scan_section_gives_empty_exclude_dirs(self):
        p = self._write_toml('[watch]\nenabled = true\n')
        cfg = load(p)
        assert cfg.scan.exclude_dirs == []

    def test_roots_still_works_alongside_exclude_dirs(self):
        p = self._write_toml(
            '[scan]\nroots = ["~/projects"]\nexclude_dirs = ["Archive"]\n'
        )
        cfg = load(p)
        assert cfg.scan.roots == ["~/projects"]
        assert cfg.scan.exclude_dirs == ["Archive"]


# ---------------------------------------------------------------------------
# load() — existing keys unaffected
# ---------------------------------------------------------------------------

class TestLoadExistingKeys:
    def _write_toml(self, content: str) -> Path:
        f = tempfile.NamedTemporaryFile(suffix=".toml", mode="w", delete=False)
        f.write(content)
        f.close()
        return Path(f.name)

    def test_watch_section_still_parsed(self):
        p = self._write_toml('[watch]\nenabled = false\ninterval_seconds = 10\n')
        cfg = load(p)
        assert cfg.watch.enabled is False
        assert cfg.watch.interval_seconds == 10

    def test_stale_section_still_parsed(self):
        p = self._write_toml('[stale]\nweeks = 4\n')
        cfg = load(p)
        assert cfg.stale.weeks == 4

    def test_bulk_section_still_parsed(self):
        p = self._write_toml('[bulk]\nmax_workers = 4\n')
        cfg = load(p)
        assert cfg.bulk.max_workers == 4

    def test_digest_section_still_parsed(self):
        p = self._write_toml('[digest]\ndefault_window = "7d"\n')
        cfg = load(p)
        assert cfg.digest.default_window == "7d"

    def test_author_section_still_parsed(self):
        p = self._write_toml('[author]\nemails = ["me@example.com"]\n')
        cfg = load(p)
        assert cfg.author.emails == ["me@example.com"]


# ---------------------------------------------------------------------------
# load() — error resilience
# ---------------------------------------------------------------------------

class TestLoadResilience:
    def test_missing_file_returns_defaults(self, tmp_path):
        cfg = load(tmp_path / "nonexistent.toml")
        assert cfg.scan.exclude_dirs == []
        assert cfg.scan.roots == []

    def test_malformed_toml_returns_defaults(self, tmp_path):
        bad = tmp_path / "bad.toml"
        bad.write_text("this is not [ valid toml !!!")
        cfg = load(bad)
        assert isinstance(cfg, GitPulseConfig)
        assert cfg.scan.exclude_dirs == []

    def test_empty_toml_returns_defaults(self, tmp_path):
        empty = tmp_path / "empty.toml"
        empty.write_text("")
        cfg = load(empty)
        assert cfg.scan.exclude_dirs == []


# ---------------------------------------------------------------------------
# _EXAMPLE_CONTENT documents exclude_dirs
# ---------------------------------------------------------------------------

class TestExampleContent:
    def test_example_content_mentions_exclude_dirs(self):
        assert "exclude_dirs" in _EXAMPLE_CONTENT

    def test_example_content_has_scan_section(self):
        assert "[scan]" in _EXAMPLE_CONTENT
