"""
sidebar.py — Repo list sidebar widget for GitPulse.

Displays all discovered repositories in a scrollable ListView with
color-coded status badges and branch names, rendered using Rich markup
inside a single Static widget per row for reliable layout.
"""

from __future__ import annotations

from pathlib import Path

from rich.text import Text

from textual.app import ComposeResult
from textual.message import Message
from textual.widgets import Static, ListView, ListItem

from git_ops import RepoInfo, RepoStatus


# ---------------------------------------------------------------------------
# Badge styles  (Rich markup)
# ---------------------------------------------------------------------------

_BADGE_MARKUP = {
    RepoStatus.CLEAN:     "[bold white on #2d7d46] ● CLEAN [/]",
    RepoStatus.MODIFIED:  "[bold #1a1b26 on #e0af68] ● MODIFIED [/]",
    RepoStatus.UNTRACKED: "[bold white on #db4b4b] ● UNTRACKED [/]",
}


# ---------------------------------------------------------------------------
# Repo list item — single Static with Rich markup
# ---------------------------------------------------------------------------

class RepoListItem(ListItem):
    """A single row in the sidebar representing one git repository."""

    DEFAULT_CSS = """
    RepoListItem {
        height: auto;
        padding: 0 1;
        margin: 0 0 0 0;
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
        badge = _BADGE_MARKUP[info.status]
        # Build a two-line display per repo:
        #   Line 1: repo name  +  badge
        #   Line 2: branch icon + branch name
        line1 = f"[bold #c0caf5]{info.name}[/]  {badge}"
        line2 = f"  [#bb9af7] {info.branch}[/]"
        yield Static(f"{line1}\n{line2}", markup=True)


# ---------------------------------------------------------------------------
# Sidebar container
# ---------------------------------------------------------------------------

class RepoSidebar(Static):
    """
    Left sidebar panel: title bar + scrollable list of repos.

    Posts a `RepoSidebar.RepoSelected` message when the user highlights
    a different repo.
    """

    class RepoSelected(Message):
        """Fired when the user selects a repo from the list."""

        def __init__(self, repo_info: RepoInfo) -> None:
            super().__init__()
            self.repo_info = repo_info

    def compose(self) -> ComposeResult:
        yield Static("⚡ [bold #7aa2f7]GitPulse[/]", id="sidebar-title", markup=True)
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
