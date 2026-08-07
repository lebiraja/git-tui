"""
Behavioural coverage for the TUI, driven through Textual's test pilot.

These exercise the interaction defects fixed alongside them, so a regression
shows up as a failing test rather than a bug report.
"""

from __future__ import annotations

import pytest
from textual.widgets import Input, ListView

from gitpulse.main import GitPulseApp
from gitpulse.ui.error_log import ErrorLogScreen
from gitpulse.ui.sidebar import RepoSidebar, _fit, column_widths

async def _booted(fleet, size=(140, 40)):
    """Yield an app with its initial scan complete."""
    app = GitPulseApp(root_dir=fleet, commits=5, watch=False)
    return app


async def _await_scan(app, pilot) -> None:
    """Block until the initial scan has populated the sidebar."""
    for _ in range(50):
        if app._all_repos and app._selected_repo is not None:
            break
        await pilot.pause(0.1)
    assert app._all_repos, "scan did not complete"
    # Let the sidebar finish populating before anything touches the list.
    await pilot.pause()


async def _highlight(app, pilot, name: str):
    """Move the sidebar highlight to the repo called *name* and settle.

    Setting ``ListView.index`` posts a Highlighted message, so the selection
    lands only once the message pump has run; poll until it does rather than
    guessing at a fixed number of pauses.
    """
    lv = app.query_one("#repo-list", ListView)
    index = next(i for i, r in enumerate(app.repos) if r.name == name)
    lv.index = index
    for _ in range(20):
        if app._selected_repo is not None and app._selected_repo.name == name:
            break
        await pilot.pause(0.05)
    assert app._selected_repo.name == name, (
        f"highlight did not land on {name!r}; got {app._selected_repo.name!r}"
    )
    return app.repos[index]


class TestFilterPreservesSelection:
    async def test_filter_keeps_the_selected_repo(self, fleet):
        """Narrowing the filter must not yank the user off their repo."""
        app = await _booted(fleet)
        async with app.run_test(size=(140, 40)) as pilot:
            # Arrange — select a specific repo by name
            await _await_scan(app, pilot)
            target = await _highlight(app, pilot, "dirty")

            # Act — filter by a substring the selected repo still matches
            app._apply_filter("dir")
            await pilot.pause()

            # Assert
            assert app._selected_repo.path == target.path

    async def test_selection_moves_when_filtered_out(self, fleet):
        app = await _booted(fleet)
        async with app.run_test(size=(140, 40)) as pilot:
            # Arrange
            await _await_scan(app, pilot)
            await _highlight(app, pilot, "dirty")

            # Act — a filter that excludes the current selection
            app._apply_filter("committed")
            await pilot.pause()

            # Assert
            assert app._selected_repo.name == "committed"

    async def test_typing_in_search_does_not_reset_each_keystroke(self, fleet):
        app = await _booted(fleet)
        async with app.run_test(size=(140, 40)) as pilot:
            # Arrange
            await _await_scan(app, pilot)
            selected = await _highlight(app, pilot, "committed")
            app.query_one("#search-input", Input).focus()
            await pilot.pause()

            # Act — type a prefix the selection still matches
            for ch in "com":
                await pilot.press(ch)
                await pilot.pause()

            # Assert
            assert app._selected_repo.path == selected.path


class TestVimNavigation:
    async def test_j_and_k_move_the_highlight(self, fleet):
        app = await _booted(fleet)
        async with app.run_test(size=(140, 40)) as pilot:
            # Arrange
            await _await_scan(app, pilot)
            lv = app.query_one("#repo-list", ListView)
            lv.index = 0
            await pilot.pause()

            # Act
            await pilot.press("j")
            await pilot.pause()
            after_down = lv.index
            await pilot.press("k")
            await pilot.pause()

            # Assert
            assert after_down == 1
            assert lv.index == 0

    async def test_j_clamps_at_the_last_row(self, fleet):
        app = await _booted(fleet)
        async with app.run_test(size=(140, 40)) as pilot:
            # Arrange
            await _await_scan(app, pilot)
            lv = app.query_one("#repo-list", ListView)

            # Act — press well past the end
            for _ in range(10):
                await pilot.press("j")
            await pilot.pause()

            # Assert
            assert lv.index == len(app.repos) - 1

    async def test_j_types_into_the_search_box_when_focused(self, fleet):
        """Vim keys must not steal keystrokes from the filter input."""
        app = await _booted(fleet)
        async with app.run_test(size=(140, 40)) as pilot:
            # Arrange
            await _await_scan(app, pilot)
            search = app.query_one("#search-input", Input)
            search.focus()
            await pilot.pause()

            # Act
            await pilot.press("j")
            await pilot.pause()

            # Assert
            assert search.value == "j"


class TestErrorLog:
    async def test_e_opens_the_error_log(self, fleet):
        app = await _booted(fleet)
        async with app.run_test(size=(140, 40)) as pilot:
            # Arrange
            await _await_scan(app, pilot)
            app._record_error("something broke")

            # Act
            await pilot.press("e")
            await pilot.pause()

            # Assert
            assert isinstance(app.screen, ErrorLogScreen)

    async def test_escape_closes_the_error_log(self, fleet):
        app = await _booted(fleet)
        async with app.run_test(size=(140, 40)) as pilot:
            # Arrange
            await _await_scan(app, pilot)
            await pilot.press("e")
            await pilot.pause()

            # Act
            await pilot.press("escape")
            await pilot.pause()

            # Assert
            assert not isinstance(app.screen, ErrorLogScreen)

    async def test_opens_cleanly_with_no_errors_recorded(self, fleet):
        app = await _booted(fleet)
        async with app.run_test(size=(140, 40)) as pilot:
            # Arrange
            await _await_scan(app, pilot)

            # Act
            await pilot.press("e")
            await pilot.pause()

            # Assert
            assert isinstance(app.screen, ErrorLogScreen)


class TestErrorRingBuffer:
    def test_records_details(self):
        app = GitPulseApp(root_dir=".", watch=False)
        app._record_error("boom")
        assert app._error_log == ["boom"]

    def test_ignores_empty_details(self):
        app = GitPulseApp(root_dir=".", watch=False)
        app._record_error("")
        assert app._error_log == []

    def test_caps_at_fifty_entries(self):
        app = GitPulseApp(root_dir=".", watch=False)
        for i in range(60):
            app._record_error(f"error {i}")
        assert len(app._error_log) == 50
        assert app._error_log[-1] == "error 59"


class TestSidebarLayout:
    def test_columns_fill_the_available_width(self):
        from gitpulse.ui.sidebar import _ROW_CHROME

        for avail in (34, 44, 54, 80):
            w_repo, w_branch = column_widths(avail)
            assert w_repo + w_branch + _ROW_CHROME == avail

    def test_columns_grow_with_available_width(self):
        narrow_repo, _ = column_widths(38)
        wide_repo, _ = column_widths(80)
        assert wide_repo > narrow_repo

    def test_columns_have_floors_on_tiny_widths(self):
        w_repo, w_branch = column_widths(10)
        assert w_repo >= 10
        assert w_branch >= 8

    def test_fit_pads_short_values(self):
        assert _fit("ab", 5) == "ab   "

    def test_fit_truncates_with_ellipsis(self):
        assert _fit("abcdef", 4) == "abc…"

    def test_fit_handles_degenerate_widths(self):
        assert _fit("abc", 0) == ""
        assert _fit("abc", 1) == "…"


class TestFleetStrip:
    async def test_all_chips_are_visible_on_a_narrow_terminal(self, fleet):
        """Every counter must render — a clipped chip hides fleet state."""
        from gitpulse.ui.fleet_status import FleetChip, FleetStatus

        app = GitPulseApp(root_dir=fleet, commits=5, watch=False)
        async with app.run_test(size=(95, 34)) as pilot:
            # Arrange
            await _await_scan(app, pilot)
            strip = app.query_one("#fleet-status", FleetStatus)
            chips = list(strip.query(FleetChip))

            # Act — total width the chips need, including their margins
            needed = sum(len(str(c.render())) + 1 for c in chips)

            # Assert — the six chips fit the strip's content area
            assert len(chips) == 6
            assert needed <= strip.container_size.width + 1, (
                f"chips need {needed} cols but only "
                f"{strip.container_size.width} are available"
            )

    async def test_counters_reflect_the_fleet(self, fleet):
        from gitpulse.ui.fleet_status import FleetChip, FleetStatus

        app = GitPulseApp(root_dir=fleet, commits=5, watch=False)
        async with app.run_test(size=(140, 40)) as pilot:
            # Arrange
            await _await_scan(app, pilot)

            # Act
            strip = app.query_one("#fleet-status", FleetStatus)
            dirty_chip = strip.query_one("#chip-dirty", FleetChip)

            # Assert — the fixture has exactly one repo with changes
            assert "1" in str(dirty_chip.render())
