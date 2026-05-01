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
    """Build a Rich markup badge string with icon and optional file count."""
    count = info.modified_count
    if info.status == RepoStatus.CLEAN:
        return "[bold white on #2d7d46] ✔ Clean [/]"
    elif info.status == RepoStatus.MODIFIED:
        label = f" ● Modified ({count}) " if count else " ● Modified "
        return f"[bold #1a1b26 on #e0af68]{label}[/]"
    else:  # UNTRACKED
        label = f" ○ Untracked ({count}) " if count else " ○ Untracked "
        return f"[bold white on #db4b4b]{label}[/]"


# ---------------------------------------------------------------------------
# Sparkline helper
# ---------------------------------------------------------------------------

_SPARK_CHARS = " ▁▂▃▄▅▆▇█"

def _sparkline(activity: list[int]) -> str:
    """Build a 7-char sparkline from weekly commit counts (oldest→newest)."""
    if not activity or len(activity) < 7:
        return "[dim #3b4261]▁▁▁▁▁▁▁[/]"
    mx = max(activity)
    if mx == 0:
        return "[dim #3b4261]▁▁▁▁▁▁▁[/]"
    chars = "".join(_SPARK_CHARS[min(8, int(v / mx * 8))] for v in activity)
    return f"[#7aa2f7]{chars}[/]"


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
        spark = _sparkline(info.commit_activity)

        # Line 1: repo name  +  badge
        line1 = f"[bold #c0caf5]{info.name}[/]  {badge}"
        # Line 2: branch  |  relative time  |  sparkline
        line2 = f"  [#bb9af7]⎇ {info.branch}[/]  [dim #565f89]⏱ {rel}[/]  {spark}"
        # Line 3: truncated last commit message for quick context
        commit_msg = info.last_commit_msg
        if len(commit_msg) > 36:
            commit_msg = commit_msg[:35] + "…"
        line3 = f"  [dim #565f89]💬 {commit_msg}[/]" if commit_msg else "  [dim #3b4261]no commits[/]"
        # Line 4: truncated repo path for disambiguation
        path_str = str(info.path)
        if len(path_str) > 38:
            path_str = "…" + path_str[-37:]
        line4 = f"  [dim #3b4261]{path_str}[/]"

        yield Static(f"{line1}\n{line2}\n{line3}\n{line4}", markup=True)


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

    def update_header(
        self,
        scanning: bool,
        count: int = 0,
        live: bool | None = None,
    ) -> None:
        """Update the title bar to show scanning state or repo count.

        *live* controls the watch indicator: True = green dot, False = dim dot,
        None = unchanged from last render.
        """
        title: Static = self.query_one("#sidebar-title", Static)
        if scanning:
            title.update("⚡ [bold #7aa2f7]GitPulse[/]  [dim #565f89]scanning…[/]")
            return
        count_str = (
            f"[dim #565f89]{count} repo{'s' if count != 1 else ''}[/]"
            if count else ""
        )
        if live is True:
            live_str = "  [bold #9ece6a]●live[/]"
        elif live is False:
            live_str = "  [dim #565f89]○paused[/]"
        else:
            live_str = ""
        title.update(f"⚡ [bold #7aa2f7]GitPulse[/]{live_str}  {count_str}")

    def populate(self, repos: list[RepoInfo]) -> None:
        """Clear and re-populate the repo list."""
        list_view: ListView = self.query_one("#repo-list", ListView)
        list_view.clear()

        if not repos:
            # Friendly empty state
            from textual.widgets import ListItem as _LI
            list_view.append(_LI(Static(
                "[dim italic #565f89]\n  📂  No repositories found\n"
                "      Try a different root or\n"
                "      press r to rescan\n[/]",
                markup=True,
            )))
            return

        for info in repos:
            list_view.append(RepoListItem(info))

        # Auto-select first item
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
