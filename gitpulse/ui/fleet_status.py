"""
fleet_status.py — Cross-repo fleet status bar for GitPulse.

Shows live counters (dirty, behind, unpushed, stashes, stale branches) across
all scanned repositories. Each chip is clickable and posts a FilterRequested
message so the sidebar can narrow to just the matching repos.
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.message import Message
from textual.widget import Widget
from textual.widgets import Static

try:
    from gitpulse.git_ops import RepoInfo, RepoStatus
except ImportError:
    from git_ops import RepoInfo, RepoStatus  # type: ignore[no-redef]


class FleetChip(Static):
    """A single clickable counter chip in the fleet status bar."""

    DEFAULT_CSS = """
    FleetChip {
        width: auto;
        height: 1;
        padding: 0 1;
        margin: 0 1;
        content-align: center middle;
    }
    FleetChip:hover {
        background: #283457;
    }
    """

    def __init__(self, category: str, **kwargs) -> None:
        super().__init__(**kwargs)
        self.category = category

    def on_click(self) -> None:
        self.post_message(FleetStatus.FilterRequested(self.category))


class FleetStatus(Widget):
    """
    Horizontal bar pinned above the sidebar showing cross-repo health counters.

    Counters:
    - dirty     — repos with uncommitted changes
    - behind    — total commits behind upstream (sum)
    - ahead     — repos with unpushed commits
    - stashes   — total stash entries (sum)
    - stale     — repos with stale local branches
    """

    DEFAULT_CSS = """
    FleetStatus {
        height: 3;
        background: #1e2030;
        border-bottom: heavy #3b4261;
        layout: horizontal;
        align: left middle;
        padding: 0 1;
    }
    FleetStatus > Static#fleet-label {
        width: auto;
        color: #565f89;
        margin-right: 1;
    }
    """

    class FilterRequested(Message):
        """Posted when a chip is clicked; carries the category to filter by."""

        def __init__(self, category: str) -> None:
            super().__init__()
            self.category = category

    def compose(self) -> ComposeResult:
        yield Static("fleet:", id="fleet-label", markup=False)
        yield FleetChip("dirty",   id="chip-dirty")
        yield FleetChip("behind",  id="chip-behind")
        yield FleetChip("ahead",   id="chip-ahead")
        yield FleetChip("stashes", id="chip-stashes")
        yield FleetChip("stale",   id="chip-stale")

    def on_mount(self) -> None:
        self._set_chip("chip-dirty",   "🔴", 0, "#f7768e")
        self._set_chip("chip-behind",  "↓",  0, "#f7768e")
        self._set_chip("chip-ahead",   "↑",  0, "#e0af68")
        self._set_chip("chip-stashes", "📦", 0, "#7aa2f7")
        self._set_chip("chip-stale",   "💀", 0, "#bb9af7")

    def update_counters(self, repos: list[RepoInfo]) -> None:
        """Recompute all chips from the current repo list."""
        n_dirty        = sum(1 for r in repos if r.status != RepoStatus.CLEAN)
        total_behind   = sum(r.behind for r in repos)
        n_ahead        = sum(1 for r in repos if r.ahead > 0)
        total_stashes  = sum(r.stash_count for r in repos)
        n_stale        = sum(1 for r in repos if r.has_stale_branches)

        self._set_chip("chip-dirty",   "🔴", n_dirty,       "#f7768e")
        self._set_chip("chip-behind",  "↓",  total_behind,  "#f7768e")
        self._set_chip("chip-ahead",   "↑",  n_ahead,       "#e0af68")
        self._set_chip("chip-stashes", "📦", total_stashes, "#7aa2f7")
        self._set_chip("chip-stale",   "💀", n_stale,       "#bb9af7")

    def _set_chip(self, widget_id: str, icon: str, count: int, color: str) -> None:
        chip: FleetChip = self.query_one(f"#{widget_id}", FleetChip)
        if count == 0:
            chip.update(f"[dim #565f89]{icon} 0[/]")
        else:
            chip.update(f"[bold {color}]{icon} {count}[/]")
