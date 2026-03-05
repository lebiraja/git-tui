"""
sidebar.py — Repo list sidebar widget for GitPulse.

Displays all discovered repositories in a scrollable ListView with
color-coded status badges, branch names, relative time, and file counts.
Includes a search/filter input at the top.
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.message import Message
from textual.widgets import Static, ListView, ListItem, Input

try:
    from gitpulse.git_ops import RepoInfo, RepoStatus
    from gitpulse.utils import relative_time
except ImportError:
    from git_ops import RepoInfo, RepoStatus  # type: ignore[no-redef]
    from utils import relative_time  # type: ignore[no-redef]


# ---------------------------------------------------------------------------
# Badge markup (Rich)
# ---------------------------------------------------------------------------

def _make_badge(info: RepoInfo) -> str:
    """Build a Rich markup badge string with optional file count."""
    count = info.modified_count
    if info.status == RepoStatus.CLEAN:
        return "[bold white on #2d7d46] ✓ CLEAN [/]"
    elif info.status == RepoStatus.MODIFIED:
        label = f" ✎ MODIFIED ({count}) " if count else " ✎ MODIFIED "
        return f"[bold #1a1b26 on #e0af68]{label}[/]"
    else:  # UNTRACKED
        label = f" ? UNTRACKED ({count}) " if count else " ? UNTRACKED "
        return f"[bold white on #db4b4b]{label}[/]"


# ---------------------------------------------------------------------------
# Repo list item — single Static with Rich markup
# ---------------------------------------------------------------------------

class RepoListItem(ListItem):
    """A single row in the sidebar representing one git repository."""

    DEFAULT_CSS = """
    RepoListItem {
        height: auto;
        padding: 0 1;
    }
    RepoListItem > Static {
        width: 100%;
        height: auto;
    }
    """

    def __init__(self, repo_info: RepoInfo, **kwargs) -> None:
        super().__init__(**kwargs)
        self.repo_info = repo_info

    def compose(self) -> ComposeResult:
        info = self.repo_info
        badge = _make_badge(info)
        rel = relative_time(info.last_commit_ts)

        # Line 1: repo name  +  badge
        line1 = f"[bold #c0caf5]{info.name}[/]  {badge}"
        # Line 2: branch  |  relative time
        line2 = f"  [#bb9af7] {info.branch}[/]  [dim #565f89]⏱ {rel}[/]"

        yield Static(f"{line1}\n{line2}", markup=True)


# ---------------------------------------------------------------------------
# Sidebar container
# ---------------------------------------------------------------------------

class RepoSidebar(Static):
    """
    Left sidebar panel: title + search input + scrollable list of repos.

    Posts a `RepoSidebar.RepoSelected` message when the user highlights
    a different repo, and `RepoSidebar.SearchChanged` when the filter changes.
    """

    class RepoSelected(Message):
        """Fired when the user selects a repo from the list."""
        def __init__(self, repo_info: RepoInfo) -> None:
            super().__init__()
            self.repo_info = repo_info

    class SearchChanged(Message):
        """Fired when the search filter text changes."""
        def __init__(self, query: str) -> None:
            super().__init__()
            self.query = query

    def compose(self) -> ComposeResult:
        yield Static(
            "⚡ [bold #7aa2f7]GitPulse[/]",
            id="sidebar-title",
            markup=True,
        )
        yield Input(
            placeholder="🔍 Filter repos...",
            id="search-input",
        )
        yield ListView(id="repo-list")

    def populate(self, repos: list[RepoInfo]) -> None:
        """Clear and re-populate the repo list."""
        list_view: ListView = self.query_one("#repo-list", ListView)
        list_view.clear()
        for info in repos:
            list_view.append(RepoListItem(info))

        # Auto-select first item
        if repos:
            list_view.index = 0

    def on_list_view_highlighted(self, event: ListView.Highlighted) -> None:
        """Forward the highlight event as a RepoSelected message."""
        if event.item is not None and isinstance(event.item, RepoListItem):
            self.post_message(self.RepoSelected(event.item.repo_info))

    def on_input_changed(self, event: Input.Changed) -> None:
        """Forward search input changes."""
        if event.input.id == "search-input":
            self.post_message(self.SearchChanged(event.value))

    def focus_search(self) -> None:
        """Focus the search input."""
        self.query_one("#search-input", Input).focus()
