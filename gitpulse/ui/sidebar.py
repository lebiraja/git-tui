"""
sidebar.py — Repo list sidebar widget for GitPulse.

Displays all discovered repositories as compact, single-line table rows with
columns: Repository · Branch · Changes · Status. Includes a filter input and
multi-select support for bulk operations.
"""

from __future__ import annotations

from pathlib import Path

from rich.text import Text

from textual.app import ComposeResult
from textual.message import Message
from textual.widgets import Static, ListView, ListItem, Input

try:
    from gitpulse.git_ops import RepoInfo, RepoStatus
except ImportError:
    from git_ops import RepoInfo, RepoStatus  # type: ignore[no-redef]


# ---------------------------------------------------------------------------
# Column layout — character widths, must match the header row below
# ---------------------------------------------------------------------------

_W_REPO = 13
_W_BRANCH = 11
_W_CHANGES = 2

# Palette
_TEXT = "#d1d5db"
_MUTED = "#6b7280"
_ACCENT = "#8b5cf6"
_GREEN = "#22c55e"
_YELLOW = "#f59e0b"
_RED = "#ef4444"


def _fit(value: str, width: int) -> str:
    """Truncate with an ellipsis or left-pad *value* to exactly *width* chars."""
    if len(value) > width:
        return value[: width - 1] + "…"
    return value.ljust(width)


def _status_cell(info: RepoInfo) -> tuple[str, str]:
    """Return (label, color) for a repo's status."""
    if info.status == RepoStatus.CLEAN:
        return "✓ Clean", _GREEN
    if info.status == RepoStatus.MODIFIED:
        return "● Modified", _YELLOW
    return "● Untracked", _RED


def column_header() -> Text:
    """Build the aligned column-header row shown above the list."""
    t = Text(no_wrap=True, overflow="ellipsis", style=_MUTED)
    t.append("  ")  # gutter + space
    t.append(_fit("Repository", _W_REPO))
    t.append(" ")
    t.append(_fit("Branch", _W_BRANCH))
    t.append(" ")
    t.append("Ch")
    t.append(" ")
    t.append("Status")
    return t


# ---------------------------------------------------------------------------
# Repo list item — one compact line
# ---------------------------------------------------------------------------

class RepoListItem(ListItem):
    """A single-line row in the sidebar representing one git repository."""

    def __init__(self, repo_info: RepoInfo, selected: bool = False, **kwargs) -> None:
        super().__init__(**kwargs)
        self.repo_info = repo_info
        self._selected = selected

    def compose(self) -> ComposeResult:
        info = self.repo_info
        t = Text(no_wrap=True, overflow="ellipsis")

        # Gutter: multi-select marker
        t.append("•" if self._selected else " ", style=_ACCENT)
        t.append(" ")
        # Repository
        t.append(_fit(info.name, _W_REPO), style=f"bold {_TEXT}")
        t.append(" ")
        # Branch
        t.append(_fit(info.branch, _W_BRANCH), style=_ACCENT)
        t.append(" ")
        # Changes count
        count = info.modified_count
        t.append(str(count).rjust(_W_CHANGES), style=_MUTED if count == 0 else _TEXT)
        t.append(" ")
        # Status
        label, color = _status_cell(info)
        t.append(label, style=color)

        yield Static(t)


# ---------------------------------------------------------------------------
# Sidebar container
# ---------------------------------------------------------------------------

class RepoSidebar(Static):
    """
    Left sidebar panel: title + filter input + column header + repo list.

    Posts `RepoSelected` when the highlighted repo changes, `SearchChanged`
    when the filter text changes, and `SelectionChanged` when the multi-select
    set changes.
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

    class SelectionChanged(Message):
        """Fired when the multi-select set changes."""
        def __init__(self, count: int, paths: list[Path]) -> None:
            super().__init__()
            self.count = count
            self.paths = paths

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._selected: set[Path] = set()
        self._current_repos: list[RepoInfo] = []

    # ── Multi-select API ────────────────────────────────────────────────

    def is_selected(self, path: Path) -> bool:
        return path in self._selected

    def toggle(self, path: Path) -> None:
        if path in self._selected:
            self._selected.discard(path)
        else:
            self._selected.add(path)
        self.post_message(self.SelectionChanged(
            count=len(self._selected),
            paths=list(self._selected),
        ))

    def select_all_visible(self) -> None:
        for r in self._current_repos:
            self._selected.add(r.path)
        self.post_message(self.SelectionChanged(
            count=len(self._selected),
            paths=list(self._selected),
        ))
        self.populate(self._current_repos)

    def clear_selection(self) -> None:
        self._selected.clear()
        self.post_message(self.SelectionChanged(count=0, paths=[]))
        self.populate(self._current_repos)

    def selected_repos(self) -> list[RepoInfo]:
        return [r for r in self._current_repos if r.path in self._selected]

    # ── Compose ─────────────────────────────────────────────────────────

    def compose(self) -> ComposeResult:
        yield Static("FLEET", id="sidebar-title", markup=False)
        yield Input(placeholder="Filter repos...", id="search-input")
        yield Static(column_header(), id="repo-list-header")
        yield ListView(id="repo-list")

    def update_header(
        self,
        scanning: bool,
        count: int = 0,
        live: bool | None = None,
    ) -> None:
        """Update the sidebar title: 'FLEET (N repos)' plus selection count."""
        title: Static = self.query_one("#sidebar-title", Static)
        if scanning:
            title.update("FLEET  ·  scanning…")
            return
        plural = "s" if count != 1 else ""
        text = f"FLEET ({count} repo{plural})"
        sel = len(self._selected)
        if sel > 0:
            text += f"  ·  {sel} selected"
        title.update(text)

    def populate(self, repos: list[RepoInfo], keep_path=None) -> None:
        """Clear and re-populate the repo list.

        If ``keep_path`` is given and present in ``repos``, the highlight is
        restored to that row (preserving the user's selection across rescans);
        otherwise the first row is highlighted.
        """
        self._current_repos = list(repos)
        list_view: ListView = self.query_one("#repo-list", ListView)
        list_view.clear()

        if not repos:
            list_view.append(ListItem(Static(
                "  No repositories found — press r to rescan",
                markup=False,
            )))
            return

        target_index = 0
        for i, info in enumerate(repos):
            list_view.append(RepoListItem(info, selected=info.path in self._selected))
            if keep_path is not None and info.path == keep_path:
                target_index = i

        list_view.index = target_index

    def set_active(self, path) -> None:
        """Move the highlight to the row with the given path (no-op if absent)."""
        list_view: ListView = self.query_one("#repo-list", ListView)
        for i, r in enumerate(self._current_repos):
            if r.path == path:
                if list_view.index != i:
                    list_view.index = i
                return

    def on_list_view_highlighted(self, event: ListView.Highlighted) -> None:
        """Forward the highlight event as a RepoSelected message."""
        if event.item is not None and isinstance(event.item, RepoListItem):
            self.post_message(self.RepoSelected(event.item.repo_info))

    def on_input_changed(self, event: Input.Changed) -> None:
        """Forward search input changes."""
        if event.input.id == "search-input":
            self.post_message(self.SearchChanged(event.value))

    def on_key(self, event) -> None:
        """Handle multi-select keys: Space toggles, * selects all."""
        if event.key == "space":
            lv: ListView = self.query_one("#repo-list", ListView)
            item = lv.highlighted_child
            if isinstance(item, RepoListItem):
                self.toggle(item.repo_info.path)
                self.populate(self._current_repos)
                event.stop()
        elif event.key == "asterisk":
            self.select_all_visible()
            event.stop()

    def focus_search(self) -> None:
        """Focus the search input."""
        self.query_one("#search-input", Input).focus()
