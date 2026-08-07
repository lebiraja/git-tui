"""Coverage for the public library surface (gitpulse.api)."""

from __future__ import annotations

import json
import subprocess
import sys

import pytest

from gitpulse.api import (
    SCHEMA_VERSION,
    fleet_to_dict,
    is_unreadable,
    repo_state,
    repo_to_dict,
    scan_fleet,
    scan_fleet_detailed,
)


class TestImportIsolation:
    def test_api_does_not_import_textual(self):
        """gitpulse.api must be importable without dragging in the TUI."""
        # Arrange
        code = (
            "import sys, gitpulse.api; "
            "bad = [m for m in sys.modules if m.split('.')[0] == 'textual']; "
            "sys.exit(1 if bad else 0)"
        )

        # Act
        result = subprocess.run([sys.executable, "-c", code])

        # Assert
        assert result.returncode == 0, "gitpulse.api pulled in textual"


class TestScanFleet:
    def test_finds_every_repo(self, fleet):
        # Act
        repos = scan_fleet(fleet)

        # Assert
        assert {r.name for r in repos} == {"clean", "dirty", "committed"}

    def test_sorted_by_most_recent_commit_first(self, fleet):
        # Act
        repos = scan_fleet(fleet)

        # Assert
        timestamps = [r.last_commit_ts for r in repos]
        assert timestamps == sorted(timestamps, reverse=True)

    def test_missing_root_raises(self, tmp_path):
        # Act / Assert
        with pytest.raises(NotADirectoryError):
            scan_fleet(tmp_path / "nope")

    def test_detailed_reports_no_errors_for_healthy_fleet(self, fleet):
        # Act
        result = scan_fleet_detailed(fleet)

        # Assert
        assert result.errors == []
        assert len(result) == 3

    def test_result_is_iterable(self, fleet):
        # Act
        result = scan_fleet_detailed(fleet)

        # Assert
        assert [r.name for r in result] == [r.name for r in result.repos]


class TestRepoState:
    def test_returns_info_for_one_repo(self, repo_path):
        # Act
        info = repo_state(repo_path)

        # Assert
        assert info.name == "solo"
        assert info.branch == "main"


class TestSerialization:
    def test_status_is_a_lowercase_string(self, repo_path):
        # Act
        payload = repo_to_dict(repo_state(repo_path))

        # Assert
        assert payload["status"] == "clean"
        assert payload["readable"] is True

    def test_last_commit_carries_epoch_and_iso(self, repo_path):
        # Act
        payload = repo_to_dict(repo_state(repo_path))

        # Assert
        assert payload["last_commit"]["ts"] > 0
        assert payload["last_commit"]["iso"].endswith("+00:00")

    def test_envelope_has_schema_version_and_counts(self, fleet):
        # Act
        payload = fleet_to_dict(scan_fleet_detailed(fleet))

        # Assert
        assert payload["schema_version"] == SCHEMA_VERSION
        assert payload["repo_count"] == 3
        assert payload["errors"] == []

    def test_envelope_is_json_serialisable(self, fleet):
        # Act
        payload = fleet_to_dict(scan_fleet_detailed(fleet))

        # Assert — must not raise
        assert json.loads(json.dumps(payload))["repo_count"] == 3

    def test_unreadable_repo_is_not_reported_as_clean(self, tmp_path):
        """A directory git cannot read must never look like a clean repo."""
        # Arrange — a .git that is not a valid repository
        broken = tmp_path / "broken"
        (broken / ".git").mkdir(parents=True)
        (broken / ".git" / "config").write_text("garbage\n")

        # Act
        payload = repo_to_dict(repo_state(broken))

        # Assert
        assert payload["status"] == "unreadable"
        assert payload["readable"] is False

    def test_is_unreadable_false_for_real_repo(self, repo_path):
        # Act / Assert
        assert is_unreadable(repo_state(repo_path)) is False
