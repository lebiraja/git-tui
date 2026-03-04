"""
tabs.py — Main panel tabs for GitPulse.

Provides Status, Commits, Diff, and Branches tabs wrapped in a
TabbedContent widget. Each tab fetches and displays data for the
currently selected repository.
"""

from __future__ import annotations

from pathlib import Path

from rich.syntax import Syntax
from rich.text import Text

from textual.app import ComposeResult
from textual.message import Message
from textual.widgets import (
    Static,
    TabbedContent,
    TabPane,
    DataTable,
    ListView,
    ListItem,
)

from git_ops import (
    get_status,
    get_commits,
    get_diff,
    get_branches,
    BranchInfo,
)


# ── Icons ──────────────────────────────────────────────────────────────────
_ICON_STAGED = "✅"
_ICON_UNSTAGED = "✏️ "
_ICON_UNTRACKED = "❓"


# ===================================================================
# Branch list item
# ===================================================================

class BranchListItem(ListItem):
    """A single branch row in the Branches tab."""

    DEFAULT_CSS = """
    BranchListItem {
        height: auto;
        padding: 0 1;
    }
    """

    def __init__(self, branch_info: BranchInfo, **kwargs) -> None:
        super().__init__(**kwargs)
        self.branch_info = branch_info

    def compose(self) -> ComposeResult:
        if self.branch_info.is_current:
            label = f"[bold #9ece6a]● {self.branch_info.name}[/]  [dim italic](current)[/]"
        else:
            label = f"[#a9b1d6]  {self.branch_info.name}[/]"
        yield Static(label, markup=True)


# ===================================================================
# Main tabbed panel
# ===================================================================

class MainPanel(Static):
    """
    Right-hand panel containing four tabs:
    Status, Commits, Diff, and Branches.
    """

    class BranchSwitchRequested(Message):
        """Posted when the user presses Enter on a branch."""

        def __init__(self, branch_name: str) -> None:
            super().__init__()
            self.branch_name = branch_name

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._current_repo: Path | None = None

    def compose(self) -> ComposeResult:
        with TabbedContent("📋 Status", "📝 Commits", "🔀 Diff", "🌿 Branches"):
            # ── Status Tab ──
            with TabPane("📋 Status", id="tab-status"):
                yield Static(
                    "[dim italic]← Select a repository to view status[/]",
                    id="status-content",
                    markup=True,
                )

            # ── Commits Tab ──
            with TabPane("📝 Commits", id="tab-commits"):
                yield DataTable(id="commits-table")

            # ── Diff Tab ──
            with TabPane("🔀 Diff", id="tab-diff"):
                yield Static(
                    "[dim italic]← Select a repository to view diff[/]",
                    id="diff-content",
                    markup=True,
                )

            # ── Branches Tab ──
            with TabPane("🌿 Branches", id="tab-branches"):
                yield ListView(id="branch-list")

    def on_mount(self) -> None:
        """Set up the commits DataTable columns."""
        table: DataTable = self.query_one("#commits-table", DataTable)
        table.add_columns("Hash", "Author", "Date", "Message")
        table.cursor_type = "row"
        table.zebra_stripes = True

    # -----------------------------------------------------------------
    # Public: load data for a repo
    # -----------------------------------------------------------------

    def load_repo(self, repo_path: Path) -> None:
        """Fetch and display data for the given repository."""
        self._current_repo = repo_path
        self._load_status(repo_path)
        self._load_commits(repo_path)
        self._load_diff(repo_path)
        self._load_branches(repo_path)

    # -----------------------------------------------------------------
    # Tab loaders
    # -----------------------------------------------------------------

    def _load_status(self, repo_path: Path) -> None:
        """Populate the Status tab."""
        fs = get_status(repo_path)
        lines: list[str] = []

        lines.append(f"[bold #7aa2f7]Repository:[/] [bold]{repo_path.name}[/]")
        lines.append("")

        if fs.staged:
            lines.append(f"[bold #9ece6a]━━ Staged ({len(fs.staged)}) ━━[/]")
            for f in fs.staged:
                lines.append(f"  {_ICON_STAGED}  {f}")
            lines.append("")

        if fs.unstaged:
            lines.append(f"[bold #e0af68]━━ Unstaged ({len(fs.unstaged)}) ━━[/]")
            for f in fs.unstaged:
                lines.append(f"  {_ICON_UNSTAGED}  {f}")
            lines.append("")

        if fs.untracked:
            lines.append(f"[bold #f7768e]━━ Untracked ({len(fs.untracked)}) ━━[/]")
            for f in fs.untracked:
                lines.append(f"  {_ICON_UNTRACKED}  {f}")
            lines.append("")

        if not fs.staged and not fs.unstaged and not fs.untracked:
            lines.append("[bold #9ece6a]✨ Working tree clean — nothing to commit[/]")

        content = self.query_one("#status-content", Static)
        content.remove_class("empty-message")
        content.update("\n".join(lines))

    def _load_commits(self, repo_path: Path) -> None:
        """Populate the Commits DataTable."""
        table: DataTable = self.query_one("#commits-table", DataTable)
        table.clear()

        commits = get_commits(repo_path)
        if not commits:
            table.add_row("—", "No commits", "", "")
            return

        for c in commits:
            table.add_row(
                c.short_hash,
                c.author,
                c.date,
                c.message,
            )

    def _load_diff(self, repo_path: Path) -> None:
        """Populate the Diff tab with syntax-highlighted output."""
        diff_text = get_diff(repo_path)
        content = self.query_one("#diff-content", Static)
        content.remove_class("empty-message")

        if diff_text.startswith("No uncommitted"):
            content.update(f"[dim italic]{diff_text}[/]")
        else:
            syntax = Syntax(
                diff_text,
                "diff",
                theme="monokai",
                line_numbers=True,
                word_wrap=True,
            )
            content.update(syntax)

    def _load_branches(self, repo_path: Path) -> None:
        """Populate the Branches ListView."""
        branch_list: ListView = self.query_one("#branch-list", ListView)
        branch_list.clear()

        branches = get_branches(repo_path)
        if not branches:
            branch_list.append(
                ListItem(Static("[dim italic]No branches found[/]", markup=True))
            )
            return

        for b in branches:
            branch_list.append(BranchListItem(b))

    # -----------------------------------------------------------------
    # Events
    # -----------------------------------------------------------------

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        """Handle Enter key on a branch item."""
        if (
            event.list_view.id == "branch-list"
            and isinstance(event.item, BranchListItem)
        ):
            self.post_message(
                self.BranchSwitchRequested(event.item.branch_info.name)
            )
