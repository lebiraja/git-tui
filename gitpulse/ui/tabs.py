"""
tabs.py — Main panel tabs for GitPulse.

Provides Status, Commits, Diff, Branches, Remotes, and Tags tabs wrapped
in a TabbedContent widget. Each tab fetches and displays data for the
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
    get_stashes,
    get_remotes,
    get_tags,
    relative_time,
    BranchInfo,
    RepoInfo,
)


# ── Icons ──────────────────────────────────────────────────────────────────
_ICON_STAGED = "✅"
_ICON_UNSTAGED = "✏️ "
_ICON_UNTRACKED = "❓"
_ICON_STASH = "📦"


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
    Right-hand panel containing six tabs:
    Status, Commits, Diff, Branches, Remotes, Tags.
    """

    class BranchSwitchRequested(Message):
        """Posted when the user presses Enter on a branch."""
        def __init__(self, branch_name: str) -> None:
            super().__init__()
            self.branch_name = branch_name

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._current_repo: Path | None = None
        self._current_info: RepoInfo | None = None

    def compose(self) -> ComposeResult:
        with TabbedContent(
            "📋 Status",
            "📝 Commits",
            "🔀 Diff",
            "🌿 Branches",
            "🌐 Remotes",
            "🏷️ Tags",
        ):
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

            # ── Remotes Tab ──
            with TabPane("🌐 Remotes", id="tab-remotes"):
                yield Static(
                    "[dim italic]← Select a repository to view remotes[/]",
                    id="remotes-content",
                    markup=True,
                )

            # ── Tags Tab ──
            with TabPane("🏷️ Tags", id="tab-tags"):
                yield DataTable(id="tags-table")

    def on_mount(self) -> None:
        """Set up DataTable columns."""
        # Commits table
        commits_table: DataTable = self.query_one("#commits-table", DataTable)
        commits_table.add_columns("Hash", "Author", "Date", "Message", "Files", "+/-")
        commits_table.cursor_type = "row"
        commits_table.zebra_stripes = True

        # Tags table
        tags_table: DataTable = self.query_one("#tags-table", DataTable)
        tags_table.add_columns("Tag", "Date", "Tagger", "Message")
        tags_table.cursor_type = "row"
        tags_table.zebra_stripes = True

    # -----------------------------------------------------------------
    # Public: load data for a repo
    # -----------------------------------------------------------------

    def load_repo(self, repo_path: Path, repo_info: RepoInfo | None = None) -> None:
        """Fetch and display data for the given repository."""
        self._current_repo = repo_path
        self._current_info = repo_info
        self._load_status(repo_path, repo_info)
        self._load_commits(repo_path)
        self._load_diff(repo_path)
        self._load_branches(repo_path)
        self._load_remotes(repo_path)
        self._load_tags(repo_path)

    # -----------------------------------------------------------------
    # Tab loaders
    # -----------------------------------------------------------------

    def _load_status(self, repo_path: Path, info: RepoInfo | None) -> None:
        """Populate the Status tab with summary header, file lists, and stashes."""
        fs = get_status(repo_path)
        stashes = get_stashes(repo_path)
        lines: list[str] = []

        # ── Repo summary header ──
        lines.append("[bold #7aa2f7]━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━[/]")
        lines.append(f"[bold #7aa2f7]  Repository:[/]  [bold]{repo_path.name}[/]")
        lines.append(f"[bold #7aa2f7]  Path:[/]        [dim]{repo_path}[/]")

        if info:
            rel = relative_time(info.last_commit_ts)
            lines.append(f"[bold #7aa2f7]  Branch:[/]      [#bb9af7]{info.branch}[/]")
            lines.append(
                f"[bold #7aa2f7]  Last commit:[/] [dim]{info.last_commit_msg}[/] [dim #565f89]({rel})[/]"
            )
            lines.append(
                f"[bold #7aa2f7]  Stats:[/]       "
                f"[#9ece6a]{info.total_commits}[/] commits · "
                f"[#e0af68]{info.contributor_count}[/] contributor{'s' if info.contributor_count != 1 else ''}"
            )

        lines.append("[bold #7aa2f7]━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━[/]")
        lines.append("")

        # ── File status ──
        if fs.staged:
            lines.append(f"[bold #9ece6a]┌─ Staged ({len(fs.staged)}) ─────────────────[/]")
            for f in fs.staged:
                lines.append(f"[#9ece6a]│[/]  {_ICON_STAGED}  {f}")
            lines.append("[#9ece6a]└──────────────────────────────[/]")
            lines.append("")

        if fs.unstaged:
            lines.append(f"[bold #e0af68]┌─ Unstaged ({len(fs.unstaged)}) ───────────────[/]")
            for f in fs.unstaged:
                lines.append(f"[#e0af68]│[/]  {_ICON_UNSTAGED}  {f}")
            lines.append("[#e0af68]└──────────────────────────────[/]")
            lines.append("")

        if fs.untracked:
            lines.append(f"[bold #f7768e]┌─ Untracked ({len(fs.untracked)}) ──────────────[/]")
            for f in fs.untracked:
                lines.append(f"[#f7768e]│[/]  {_ICON_UNTRACKED}  {f}")
            lines.append("[#f7768e]└──────────────────────────────[/]")
            lines.append("")

        if not fs.staged and not fs.unstaged and not fs.untracked:
            lines.append("[bold #9ece6a]  ✨ Working tree clean — nothing to commit[/]")
            lines.append("")

        # ── Stashes ──
        if stashes:
            lines.append(f"[bold #7dcfff]┌─ Stashes ({len(stashes)}) ───────────────────[/]")
            for s in stashes:
                lines.append(f"[#7dcfff]│[/]  {_ICON_STASH} stash@{{{s.index}}}: {s.message}")
            lines.append("[#7dcfff]└──────────────────────────────[/]")

        content = self.query_one("#status-content", Static)
        content.remove_class("empty-message")
        content.update("\n".join(lines))

    def _load_commits(self, repo_path: Path) -> None:
        """Populate the Commits DataTable with stats."""
        table: DataTable = self.query_one("#commits-table", DataTable)
        table.clear()

        commits = get_commits(repo_path)
        if not commits:
            table.add_row("—", "No commits", "", "", "", "")
            return

        for c in commits:
            # Format +/- as colored text
            plus_minus = f"+{c.insertions} -{c.deletions}"
            table.add_row(
                c.short_hash,
                c.author,
                c.date,
                c.message[:60],
                str(c.files_changed),
                plus_minus,
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

    def _load_remotes(self, repo_path: Path) -> None:
        """Populate the Remotes tab."""
        remotes = get_remotes(repo_path)
        lines: list[str] = []

        if not remotes:
            lines.append("[dim italic]No remotes configured[/]")
        else:
            for r in remotes:
                lines.append(f"[bold #7aa2f7]━━ {r.name} ━━[/]")
                lines.append(f"  [bold]URL:[/]   [dim]{r.url}[/]")

                # Ahead/behind display
                if r.ahead or r.behind:
                    parts = []
                    if r.ahead:
                        parts.append(f"[bold #9ece6a]↑ {r.ahead} ahead[/]")
                    if r.behind:
                        parts.append(f"[bold #f7768e]↓ {r.behind} behind[/]")
                    lines.append(f"  [bold]Sync:[/]  {' · '.join(parts)}")
                else:
                    lines.append(f"  [bold]Sync:[/]  [#9ece6a]✓ Up to date[/]")
                lines.append("")

        content = self.query_one("#remotes-content", Static)
        content.remove_class("empty-message")
        content.update("\n".join(lines))

    def _load_tags(self, repo_path: Path) -> None:
        """Populate the Tags DataTable."""
        table: DataTable = self.query_one("#tags-table", DataTable)
        table.clear()

        tags = get_tags(repo_path)
        if not tags:
            table.add_row("—", "No tags", "", "")
            return

        for t in tags:
            table.add_row(t.name, t.date, t.tagger, t.message[:60])

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
