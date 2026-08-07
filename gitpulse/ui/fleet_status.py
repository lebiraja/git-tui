"""
fleet_status.py — Cross-repo fleet status strip for GitPulse.

A quiet single-line strip of clickable counters (dirty, behind, ahead,
stashes, stale) across all scanned repositories. Each chip posts a
FilterRequested message so the sidebar can narrow to matching repos.
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.message import Message
from textual.widgets import Static

from ..git_ops import RepoInfo, RepoStatus


_CHIP_TOOLTIPS = {
    "dirty": "Repos with uncommitted changes",
    "behind": "Total commits behind upstream",
    "ahead": "Repos with unpushed commits",
    "stashes": "Total stash entries",
    "stale": "Repos with stale branches",
    "all": "Clear the filter",
}


class FleetChip(Static):
    """A single clickable counter chip in the fleet status strip."""

    def __init__(self, category: str, **kwargs) -> None:
        super().__init__(**kwargs)
        self.category = category
        # Labels are abbreviated to fit a narrow sidebar; the tooltip carries
        # the full meaning so the strip stays discoverable.
        self.tooltip = _CHIP_TOOLTIPS.get(category)

    def on_click(self) -> None:
        self.post_message(FleetStatus.FilterRequested(self.category))


class FleetStatus(Horizontal):
    """
    Quiet single-row strip above the sidebar showing cross-repo counters.

    Counters: dirty, behind, ahead, stashes, stale — plus an 'all' reset chip.
    Clicking a chip filters the sidebar to the matching repos.
    """

    class FilterRequested(Message):
        """Posted when a chip is clicked; carries the category to filter by."""

        def __init__(self, category: str) -> None:
            super().__init__()
            self.category = category

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._active_filter: str = ""

    def compose(self) -> ComposeResult:
        yield FleetChip("dirty",   id="chip-dirty")
        yield FleetChip("behind",  id="chip-behind")
        yield FleetChip("ahead",   id="chip-ahead")
        yield FleetChip("stashes", id="chip-stashes")
        yield FleetChip("stale",   id="chip-stale")
        yield FleetChip("all",     id="chip-all")

    def on_mount(self) -> None:
        self.update_counters([])
        self.query_one("#chip-all", FleetChip).update("[#6b7280]all[/]")

    def update_counters(self, repos: list[RepoInfo]) -> None:
        """Recompute all chips from the current repo list."""
        n_dirty       = sum(1 for r in repos if r.status != RepoStatus.CLEAN)
        total_behind  = sum(r.behind for r in repos)
        n_ahead       = sum(1 for r in repos if r.ahead > 0)
        total_stashes = sum(r.stash_count for r in repos)
        n_stale       = sum(1 for r in repos if r.has_stale_branches)

        # Short labels: six chips must fit a sidebar of ~31 usable columns.
        # Tooltips carry the full meaning of each abbreviation.
        self._set_chip("chip-dirty",   "dirty", n_dirty,       "#f59e0b")
        self._set_chip("chip-behind",  "↓",     total_behind,  "#ef4444")
        self._set_chip("chip-ahead",   "↑",     n_ahead,       "#22c55e")
        self._set_chip("chip-stashes", "stsh",  total_stashes, "#8b5cf6")
        self._set_chip("chip-stale",   "stl",   n_stale,       "#6b7280")

    def set_active_filter(self, category: str) -> None:
        """Highlight the active filter chip and clear the others."""
        self._active_filter = category
        chip_map = {
            "dirty": "chip-dirty", "behind": "chip-behind",
            "ahead": "chip-ahead", "stashes": "chip-stashes",
            "stale": "chip-stale", "all": "chip-all",
        }
        for cat, cid in chip_map.items():
            chip: FleetChip = self.query_one(f"#{cid}", FleetChip)
            chip.set_class(cat == category and category not in ("all", ""), "-active-filter")

    def _set_chip(self, widget_id: str, label: str, count: int, color: str) -> None:
        chip: FleetChip = self.query_one(f"#{widget_id}", FleetChip)
        if count == 0:
            chip.update(f"[#6b7280]{label} 0[/]")
        else:
            chip.update(f"[{color}]{label} {count}[/]")
