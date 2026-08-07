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

from ..git_ops import RepoInfo, RepoStatus


# ---------------------------------------------------------------------------
# Column layout — widths are computed from the sidebar's actual width by
# column_widths(); the header and the rows both derive from it so they cannot
# drift out of alignment.
# ---------------------------------------------------------------------------

_W_CHANGES = 3

# Fixed overhead per row: gutter marker + space, space after repo, space after
# branch, the change-count column, space, status dot.
_ROW_CHROME = 2 + 1 + 1 + _W_CHANGES + 1 + 1

# Floors — below these the columns stop shrinking and truncate instead.
_MIN_REPO = 10
_MIN_BRANCH = 8

# Fallback used before the widget knows its own size.
_DEFAULT_AVAIL = 44

# Palette
_TEXT = "#d1d5db"
_MUTED = "#6b7280"
_ACCENT = "#8b5cf6"
_GREEN = "#22c55e"
_YELLOW = "#f59e0b"
_RED = "#ef4444"


def _fit(value: str, width: int) -> str:
    """Truncate with an ellipsis or left-pad *value* to exactly *width* chars."""
    if width <= 0:
        return ""
    if len(value) > width:
        if width == 1:
            return "…"
        return value[: width - 1] + "…"
    return value.ljust(width)


def column_widths(avail: int) -> tuple[int, int]:
    """Split *avail* columns between the repo-name and branch columns.

    Widths are derived from the sidebar's real width rather than hardcoded, so
    the row fills the panel at any size instead of truncating at a fixed 16/15
    while the container flexes.
    """
    flex = avail - _ROW_CHROME
    if flex < _MIN_REPO + _MIN_BRANCH:
        return _MIN_REPO, _MIN_BRANCH
    w_repo = max(_MIN_REPO, int(flex * 0.55))
    w_branch = max(_MIN_BRANCH, flex - w_repo)
    return w_repo, w_branch


def _status_dot(info: RepoInfo) -> tuple[str, str]:
    """Return (glyph, color) for a repo's status — a single compact dot.

    The dot's colour carries the status (green=clean, yellow=modified,
    red=untracked); the separate change-count column carries magnitude.
    This frees the horizontal room the old "● Modified" label wasted.
    """
    if info.status == RepoStatus.CLEAN:
        return "✓", _GREEN
    if info.status == RepoStatus.MODIFIED:
        return "●", _YELLOW
    return "●", _RED


def column_header(avail: int = _DEFAULT_AVAIL) -> Text:
    """Build the aligned column-header row shown above the list."""
    w_repo, w_branch = column_widths(avail)
    t = Text(no_wrap=True, overflow="ellipsis", style=_MUTED)
    t.append("  ")  # gutter + space
    t.append(_fit("Repository", w_repo))
    t.append(" ")
    t.append(_fit("Branch", w_branch))
    t.append(" ")
    t.append("Δ".rjust(_W_CHANGES))
    t.append(" ")
    t.append("·")
    return t


# ---------------------------------------------------------------------------
# Repo list item — one compact line
# ---------------------------------------------------------------------------

class RepoListItem(ListItem):
    """A single-line row in the sidebar representing one git repository."""

    def __init__(
        self,
        repo_info: RepoInfo,
        selected: bool = False,
        avail: int = _DEFAULT_AVAIL,
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self.repo_info = repo_info
        self._selected = selected
        self._avail = avail

    def compose(self) -> ComposeResult:
        info = self.repo_info
        w_repo, w_branch = column_widths(self._avail)
        t = Text(no_wrap=True, overflow="ellipsis")

        # Gutter: multi-select marker
        t.append("•" if self._selected else " ", style=_ACCENT)
        t.append(" ")
        # Repository
        t.append(_fit(info.name, w_repo), style=f"bold {_TEXT}")
        t.append(" ")
        # Branch
        t.append(_fit(info.branch, w_branch), style=_ACCENT)
        t.append(" ")
        # Changes count — only show the number when there is something to show
        count = info.modified_count
        count_str = (str(count) if count else "·").rjust(_W_CHANGES)
        t.append(count_str, style=_MUTED if count == 0 else _TEXT)
        t.append(" ")
        # Status — single colour-coded dot (colour == status)
        glyph, color = _status_dot(info)
        t.append(glyph, style=f"bold {color}")

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
        self._avail: int = _DEFAULT_AVAIL  # Sidebar width, updated on resize

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
        yield Static(column_header(self._avail), id="repo-list-header")
        yield ListView(id="repo-list")

    def on_resize(self, event) -> None:
        """Recompute column widths and rebuild rows when the sidebar resizes."""
        avail = max(int(event.size.width), _ROW_CHROME + _MIN_REPO + _MIN_BRANCH)
        if avail == self._avail:
            return
        self._avail = avail
        self.query_one("#repo-list-header", Static).update(column_header(avail))
        if self._current_repos:
            lv: ListView = self.query_one("#repo-list", ListView)
            keep = lv.index
            self.populate(self._current_repos)
            if keep is not None and keep < len(self._current_repos):
                lv.index = keep

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
            list_view.append(RepoListItem(
                info, selected=info.path in self._selected, avail=self._avail,
            ))
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
        """Forward the highlight event as a RepoSelected message.

        ``populate`` clears and refills the ListView, and those mutations queue
        Highlighted events that arrive *after* it returns. Such an event can
        reference a row from the previous list, which would clobber the
        selection populate just restored — so ignore any item that is no longer
        part of the current list.
        """
        if not isinstance(event.item, RepoListItem):
            return
        if event.item.repo_info.path not in {r.path for r in self._current_repos}:
            return
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
