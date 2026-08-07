"""Coverage for the Markdown context pack (gitpulse.context)."""

from __future__ import annotations

from gitpulse.api import scan_fleet_detailed
from gitpulse.context import render_context


class TestRenderContext:
    def test_starts_with_a_timestamped_heading(self, fleet):
        # Act
        out = render_context(scan_fleet_detailed(fleet))

        # Assert
        assert out.startswith("# Fleet state — ")

    def test_reports_the_root_and_repo_count(self, fleet):
        # Act
        out = render_context(scan_fleet_detailed(fleet))

        # Assert
        assert str(fleet) in out
        assert "3 repos" in out

    def test_dirty_repo_appears_under_needs_attention(self, fleet):
        # Act
        out = render_context(scan_fleet_detailed(fleet))

        # Assert
        section = out.split("## Needs attention")[1]
        assert "dirty" in section

    def test_clean_repos_are_collapsed_into_a_name_list(self, fleet):
        # Act
        out = render_context(scan_fleet_detailed(fleet))

        # Assert
        assert "## Clean and synced" in out

    def test_max_repos_truncates_with_a_note(self, fleet):
        # Act — a cap below the number of attention repos
        out = render_context(scan_fleet_detailed(fleet), max_repos=0)

        # Assert
        assert "more" in out

    def test_output_ends_with_a_single_newline(self, fleet):
        # Act
        out = render_context(scan_fleet_detailed(fleet))

        # Assert
        assert out.endswith("\n")
        assert not out.endswith("\n\n")

    def test_unreadable_repo_is_flagged_not_counted_clean(self, tmp_path):
        """An unreadable repo must never be summarised as clean."""
        # Arrange
        root = tmp_path / "fleet"
        broken = root / "broken"
        (broken / ".git").mkdir(parents=True)
        (broken / ".git" / "config").write_text("garbage\n")

        # Act
        out = render_context(scan_fleet_detailed(root))

        # Assert
        assert "## Could not be read" in out
        assert "unknown, not clean" in out

    def test_no_markup_leaks_into_the_output(self, fleet):
        """Output is pasted into prompts — it must be plain Markdown."""
        # Act
        out = render_context(scan_fleet_detailed(fleet))

        # Assert
        assert "\x1b[" not in out
