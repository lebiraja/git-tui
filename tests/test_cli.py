"""
End-to-end coverage for the non-interactive CLI surface.

Each test runs the real console entry point in a subprocess so it exercises
argument parsing, stdout formatting, and exit codes exactly as an agent
shelling out would experience them.
"""

from __future__ import annotations

import json
import subprocess
import sys


def run_cli(*args, expect_success: bool = True) -> subprocess.CompletedProcess:
    """Invoke `python -m gitpulse ...` and return the completed process."""
    result = subprocess.run(
        [sys.executable, "-m", "gitpulse", *args],
        capture_output=True,
        text=True,
    )
    if expect_success:
        assert result.returncode == 0, result.stderr
    return result


class TestScanJson:
    def test_emits_valid_json(self, fleet):
        # Act
        result = run_cli("scan", "--root", str(fleet), "--json")

        # Assert
        payload = json.loads(result.stdout)
        assert payload["repo_count"] == 3

    def test_stdout_contains_only_json(self, fleet):
        """Nothing may pollute stdout — consumers pipe it straight to a parser."""
        # Act
        result = run_cli("scan", "--root", str(fleet), "--json")

        # Assert
        assert result.stdout.lstrip().startswith("{")
        json.loads(result.stdout)

    def test_dirty_filter_narrows_results(self, fleet):
        # Act
        result = run_cli("scan", "--root", str(fleet), "--json", "--dirty")

        # Assert
        payload = json.loads(result.stdout)
        assert [r["name"] for r in payload["repos"]] == ["dirty"]

    def test_repo_count_reflects_the_filter(self, fleet):
        # Act
        result = run_cli("scan", "--root", str(fleet), "--json", "--dirty")

        # Assert
        assert json.loads(result.stdout)["repo_count"] == 1

    def test_ndjson_emits_one_object_per_line(self, fleet):
        # Act
        result = run_cli("scan", "--root", str(fleet), "--ndjson")

        # Assert
        lines = [ln for ln in result.stdout.splitlines() if ln.strip()]
        assert len(lines) == 3
        assert all(json.loads(ln)["name"] for ln in lines)

    def test_json_and_ndjson_are_mutually_exclusive(self, fleet):
        # Act
        result = run_cli(
            "scan", "--root", str(fleet), "--json", "--ndjson",
            expect_success=False,
        )

        # Assert
        assert result.returncode != 0
        assert "not allowed with" in result.stderr

    def test_missing_root_exits_nonzero(self, tmp_path):
        # Act
        result = run_cli(
            "scan", "--root", str(tmp_path / "absent"), "--json",
            expect_success=False,
        )

        # Assert
        assert result.returncode == 1
        assert "Error" in result.stderr


class TestContext:
    def test_renders_markdown_headings(self, fleet):
        # Act
        result = run_cli("context", "--root", str(fleet))

        # Assert
        assert result.stdout.startswith("# Fleet state")
        assert "## Needs attention" in result.stdout

    def test_dirty_repo_is_listed_as_needing_attention(self, fleet):
        # Act
        result = run_cli("context", "--root", str(fleet))

        # Assert
        attention = result.stdout.split("## Needs attention")[1]
        assert "dirty" in attention


class TestDigest:
    def test_renders_a_digest(self, fleet):
        # Act
        result = run_cli(
            "digest", "--root", str(fleet),
            "--since", "7d", "--author", "test@example.com",
        )

        # Assert
        assert "Activity digest" in result.stdout

    def test_bad_time_spec_exits_nonzero(self, fleet):
        # Act
        result = run_cli(
            "digest", "--root", str(fleet), "--since", "not-a-window",
            expect_success=False,
        )

        # Assert
        assert result.returncode == 1
        assert "Unrecognised time spec" in result.stderr


class TestTopLevel:
    def test_version_flag_reports_version(self):
        # Act
        result = run_cli("--version")

        # Assert
        assert result.stdout.startswith("gitpulse ")

    def test_help_lists_the_subcommands(self):
        # Act
        result = run_cli("--help")

        # Assert
        for name in ("scan", "context", "digest"):
            assert name in result.stdout
