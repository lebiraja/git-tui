"""
Tests for gitpulse/scanner.py

Covers:
- SKIP_DIRS contents (cloud-sync + macOS system names present)
- MAX_DEPTH limits recursion
- OSError / TimeoutError / PermissionError are caught and skipped
- DirEntry.is_dir() raising OSError is handled
- os.path.ismount() True → directory skipped
- .git discovery and no deeper recursion
- Hidden dirs (dot-prefix) skipped
- extra_skip parameter (backward compat + merging)
- scan_repos on invalid paths returns []
"""

import os
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from gitpulse.scanner import SKIP_DIRS, MAX_DEPTH, scan_repos, _walk


# ---------------------------------------------------------------------------
# SKIP_DIRS contents
# ---------------------------------------------------------------------------

class TestSkipDirs:
    def test_contains_python_build_artifacts(self):
        for name in ("node_modules", "__pycache__", ".venv", "venv", "dist", "build"):
            assert name in SKIP_DIRS

    def test_contains_google_drive(self):
        assert "Google Drive" in SKIP_DIRS

    def test_contains_dropbox(self):
        assert "Dropbox" in SKIP_DIRS

    def test_contains_onedrive(self):
        assert "OneDrive" in SKIP_DIRS

    def test_contains_box(self):
        assert "Box" in SKIP_DIRS

    def test_contains_icloud_drive(self):
        assert "iCloud Drive" in SKIP_DIRS

    def test_contains_macos_library(self):
        assert "Library" in SKIP_DIRS

    def test_contains_macos_applications(self):
        assert "Applications" in SKIP_DIRS

    def test_contains_macos_movies(self):
        assert "Movies" in SKIP_DIRS

    def test_contains_macos_music(self):
        assert "Music" in SKIP_DIRS

    def test_contains_macos_pictures(self):
        assert "Pictures" in SKIP_DIRS

    def test_contains_macos_public(self):
        assert "Public" in SKIP_DIRS

    def test_is_a_set(self):
        assert isinstance(SKIP_DIRS, set)


# ---------------------------------------------------------------------------
# MAX_DEPTH
# ---------------------------------------------------------------------------

class TestMaxDepth:
    def test_max_depth_is_positive_integer(self):
        assert isinstance(MAX_DEPTH, int)
        assert MAX_DEPTH > 0

    def test_depth_limit_stops_recursion(self, tmp_path):
        # Build a chain of dirs 2 levels deeper than MAX_DEPTH
        current = tmp_path
        for i in range(MAX_DEPTH + 2):
            current = current / f"level_{i}"
            current.mkdir()
        # Place a repo at the very bottom (beyond MAX_DEPTH)
        (current / ".git").mkdir()
        result = scan_repos(tmp_path)
        # Should NOT find the repo — it's beyond MAX_DEPTH
        assert current not in result

    def test_repo_at_max_depth_is_found(self, tmp_path):
        # Build a chain exactly at MAX_DEPTH
        current = tmp_path
        for i in range(MAX_DEPTH):
            current = current / f"level_{i}"
            current.mkdir()
        (current / ".git").mkdir()
        result = scan_repos(tmp_path)
        assert current in result


# ---------------------------------------------------------------------------
# scan_repos — invalid paths
# ---------------------------------------------------------------------------

class TestScanReposInvalidPaths:
    def test_nonexistent_root_returns_empty(self, tmp_path):
        result = scan_repos(tmp_path / "does_not_exist")
        assert result == []

    def test_file_as_root_returns_empty(self, tmp_path):
        f = tmp_path / "file.txt"
        f.write_text("hello")
        result = scan_repos(f)
        assert result == []

    def test_empty_directory_returns_empty(self, tmp_path):
        result = scan_repos(tmp_path)
        assert result == []


# ---------------------------------------------------------------------------
# scan_repos — discovers git repos
# ---------------------------------------------------------------------------

class TestScanReposDiscovery:
    def test_finds_single_repo(self, tmp_path):
        repo = tmp_path / "myrepo"
        repo.mkdir()
        (repo / ".git").mkdir()
        result = scan_repos(tmp_path)
        assert repo in result

    def test_finds_multiple_repos(self, tmp_path):
        for name in ("alpha", "beta", "gamma"):
            d = tmp_path / name
            d.mkdir()
            (d / ".git").mkdir()
        result = scan_repos(tmp_path)
        assert len(result) == 3

    def test_does_not_recurse_into_repo(self, tmp_path):
        outer = tmp_path / "outer"
        outer.mkdir()
        (outer / ".git").mkdir()
        inner = outer / "inner"
        inner.mkdir()
        (inner / ".git").mkdir()
        result = scan_repos(tmp_path)
        # Only outer should be found; inner is beneath a .git boundary
        assert outer in result
        assert inner not in result

    def test_nested_repo_outside_git_boundary(self, tmp_path):
        projects = tmp_path / "projects"
        projects.mkdir()
        for name in ("a", "b"):
            d = projects / name
            d.mkdir()
            (d / ".git").mkdir()
        result = scan_repos(tmp_path)
        assert len(result) == 2

    def test_returns_list(self, tmp_path):
        assert isinstance(scan_repos(tmp_path), list)

    def test_tilde_expansion(self, tmp_path, monkeypatch):
        # scan_repos should call expanduser — just test it doesn't blow up
        # when given a resolved absolute path (tilde already expanded)
        result = scan_repos(tmp_path)
        assert isinstance(result, list)


# ---------------------------------------------------------------------------
# scan_repos — skipping rules
# ---------------------------------------------------------------------------

class TestScanReposSkipping:
    def test_skips_hidden_directories(self, tmp_path):
        hidden = tmp_path / ".hidden"
        hidden.mkdir()
        (hidden / ".git").mkdir()
        result = scan_repos(tmp_path)
        assert hidden not in result

    def test_skips_node_modules(self, tmp_path):
        nm = tmp_path / "node_modules"
        nm.mkdir()
        (nm / ".git").mkdir()
        result = scan_repos(tmp_path)
        assert nm not in result

    def test_skips_skip_dirs_names(self, tmp_path):
        for name in ("venv", "__pycache__", "dist", "build"):
            d = tmp_path / name
            d.mkdir()
            (d / ".git").mkdir()
        result = scan_repos(tmp_path)
        assert result == []

    def test_skips_google_drive(self, tmp_path):
        gd = tmp_path / "Google Drive"
        gd.mkdir()
        (gd / ".git").mkdir()
        result = scan_repos(tmp_path)
        assert gd not in result

    def test_skips_dropbox(self, tmp_path):
        db = tmp_path / "Dropbox"
        db.mkdir()
        (db / ".git").mkdir()
        result = scan_repos(tmp_path)
        assert db not in result

    def test_skips_library(self, tmp_path):
        lib = tmp_path / "Library"
        lib.mkdir()
        (lib / ".git").mkdir()
        result = scan_repos(tmp_path)
        assert lib not in result

    def test_skips_applications(self, tmp_path):
        apps = tmp_path / "Applications"
        apps.mkdir()
        (apps / ".git").mkdir()
        result = scan_repos(tmp_path)
        assert apps not in result

    def test_skips_movies(self, tmp_path):
        d = tmp_path / "Movies"
        d.mkdir()
        (d / ".git").mkdir()
        result = scan_repos(tmp_path)
        assert d not in result

    def test_extra_skip_excludes_named_dir(self, tmp_path):
        special = tmp_path / "BigArchive"
        special.mkdir()
        (special / ".git").mkdir()
        result = scan_repos(tmp_path, extra_skip={"BigArchive"})
        assert special not in result

    def test_extra_skip_does_not_affect_other_repos(self, tmp_path):
        keep = tmp_path / "keep"
        keep.mkdir()
        (keep / ".git").mkdir()
        skip_me = tmp_path / "SkipMe"
        skip_me.mkdir()
        (skip_me / ".git").mkdir()
        result = scan_repos(tmp_path, extra_skip={"SkipMe"})
        assert keep in result
        assert skip_me not in result

    def test_extra_skip_none_uses_only_skip_dirs(self, tmp_path):
        repo = tmp_path / "myrepo"
        repo.mkdir()
        (repo / ".git").mkdir()
        result = scan_repos(tmp_path, extra_skip=None)
        assert repo in result

    def test_extra_skip_empty_set_uses_only_skip_dirs(self, tmp_path):
        repo = tmp_path / "myrepo"
        repo.mkdir()
        (repo / ".git").mkdir()
        result = scan_repos(tmp_path, extra_skip=set())
        assert repo in result

    def test_skips_mount_points(self, tmp_path):
        mnt = tmp_path / "network_share"
        mnt.mkdir()
        (mnt / ".git").mkdir()
        with patch("os.path.ismount", side_effect=lambda p: str(p) == str(mnt)):
            result = scan_repos(tmp_path)
        assert mnt not in result

    def test_non_mount_normal_dir_is_not_skipped(self, tmp_path):
        repo = tmp_path / "myrepo"
        repo.mkdir()
        (repo / ".git").mkdir()
        with patch("os.path.ismount", return_value=False):
            result = scan_repos(tmp_path)
        assert repo in result


# ---------------------------------------------------------------------------
# Error handling in _walk
# ---------------------------------------------------------------------------

class TestWalkErrorHandling:
    def test_permission_error_on_scandir_is_skipped(self, tmp_path):
        locked = tmp_path / "locked"
        locked.mkdir()

        original_scandir = os.scandir
        def fake_scandir(path):
            if str(path) == str(locked):
                raise PermissionError("Access denied")
            return original_scandir(path)

        with patch("os.scandir", fake_scandir):
            result = scan_repos(tmp_path)
        assert isinstance(result, list)

    def test_timeout_error_on_scandir_is_skipped(self, tmp_path):
        slow = tmp_path / "SlowMount"
        slow.mkdir()

        original_scandir = os.scandir
        def fake_scandir(path):
            if str(path) == str(slow):
                raise TimeoutError(60, "Operation timed out")
            return original_scandir(path)

        with patch("os.scandir", fake_scandir):
            result = scan_repos(tmp_path)
        assert isinstance(result, list)

    def test_oserror_on_scandir_is_skipped(self, tmp_path):
        broken = tmp_path / "broken"
        broken.mkdir()

        original_scandir = os.scandir
        def fake_scandir(path):
            if str(path) == str(broken):
                raise OSError("I/O error")
            return original_scandir(path)

        with patch("os.scandir", fake_scandir):
            result = scan_repos(tmp_path)
        assert isinstance(result, list)

    def test_oserror_on_is_dir_entry_is_skipped(self, tmp_path):
        repo = tmp_path / "good_repo"
        repo.mkdir()
        (repo / ".git").mkdir()

        bad_child = tmp_path / "bad_child"
        bad_child.mkdir()

        original_scandir = os.scandir
        def fake_scandir(path):
            entries = list(original_scandir(path))
            for e in entries:
                if e.name == "bad_child":
                    # Wrap to make is_dir() raise
                    class BrokenEntry:
                        name = e.name
                        path = e.path
                        def is_dir(self, **kw): raise OSError("stat failed")
                    entries[entries.index(e)] = BrokenEntry()
            class FakeCtx:
                def __enter__(self_): return iter(entries)
                def __exit__(self_, *a): pass
            return FakeCtx()

        with patch("os.scandir", fake_scandir):
            result = scan_repos(tmp_path)
        assert repo in result

    def test_timeout_in_nested_dir_does_not_abort_siblings(self, tmp_path):
        slow = tmp_path / "SlowMount"
        slow.mkdir()
        good = tmp_path / "goodrepo"
        good.mkdir()
        (good / ".git").mkdir()

        original_scandir = os.scandir
        def fake_scandir(path):
            if str(path) == str(slow):
                raise TimeoutError(60, "Operation timed out")
            return original_scandir(path)

        with patch("os.scandir", fake_scandir):
            result = scan_repos(tmp_path)

        assert good in result
        assert slow not in result

    def test_multiple_errors_dont_crash(self, tmp_path):
        for i in range(5):
            d = tmp_path / f"broken_{i}"
            d.mkdir()

        original_scandir = os.scandir
        def fake_scandir(path):
            import pathlib
            if Path(path).name.startswith("broken_"):
                raise TimeoutError(60, "Timed out")
            return original_scandir(path)

        with patch("os.scandir", fake_scandir):
            result = scan_repos(tmp_path)
        assert result == []

    def test_scan_still_finds_repos_after_timeout_in_sibling(self, tmp_path):
        slow = tmp_path / "FakeCloud"
        slow.mkdir()
        (slow / ".git").mkdir()

        repo = tmp_path / "myproject"
        repo.mkdir()
        (repo / ".git").mkdir()

        original_scandir = os.scandir
        def fake_scandir(path):
            if str(path) == str(slow):
                raise TimeoutError(60, "Timed out")
            return original_scandir(path)

        with patch("os.scandir", fake_scandir):
            patched_skip = SKIP_DIRS - {"FakeCloud"}
            with patch("gitpulse.scanner.SKIP_DIRS", patched_skip):
                result = scan_repos(tmp_path)

        assert repo in result


# ---------------------------------------------------------------------------
# _walk internal — direct unit tests
# ---------------------------------------------------------------------------

class TestWalkDirect:
    def test_walk_adds_repo_to_list(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / ".git").mkdir()
        repos = []
        _walk(str(tmp_path), repos, set(), 0)
        assert repo in repos

    def test_walk_skips_name_in_skip_set(self, tmp_path):
        skip_me = tmp_path / "skip_me"
        skip_me.mkdir()
        (skip_me / ".git").mkdir()
        repos = []
        _walk(str(tmp_path), repos, {"skip_me"}, 0)
        assert skip_me not in repos

    def test_walk_skips_dot_dirs(self, tmp_path):
        hidden = tmp_path / ".hidden_repo"
        hidden.mkdir()
        (hidden / ".git").mkdir()
        repos = []
        _walk(str(tmp_path), repos, set(), 0)
        assert hidden not in repos

    def test_walk_stops_at_git_boundary(self, tmp_path):
        outer = tmp_path / "outer"
        outer.mkdir()
        (outer / ".git").mkdir()
        inner = outer / "inner"
        inner.mkdir()
        (inner / ".git").mkdir()
        repos = []
        _walk(str(tmp_path), repos, set(), 0)
        assert outer in repos
        assert inner not in repos
