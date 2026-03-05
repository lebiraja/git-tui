"""
tabs.py — Main panel tabs for GitPulse.

Provides Status, Commits, Diff, Branches, Remotes, and Tags tabs wrapped
in a TabbedContent widget. Each tab fetches and displays data for the
currently selected repository.
"""

from __future__ import annotations

from pathlib import Path

from rich.console import Group
from rich.panel import Panel
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

try:
    from gitpulse.git_ops import (
        get_status, get_commits, get_diff, get_branches,
        get_stashes, get_remotes, get_tags, get_file_tree,
        BranchInfo, RepoInfo,
    )
    from gitpulse.utils import relative_time
except ImportError:
    from git_ops import (  # type: ignore[no-redef]
        get_status, get_commits, get_diff, get_branches,
        get_stashes, get_remotes, get_tags, get_file_tree,
        BranchInfo, RepoInfo,
    )
    from utils import relative_time  # type: ignore[no-redef]


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

    def __init__(self, commits: int = 10, **kwargs) -> None:
        super().__init__(**kwargs)
        self._current_repo: Path | None = None
        self._current_info: RepoInfo | None = None
        self._commits_n = commits
        # Track which tabs have been loaded for the current repo
        self._loaded_tabs: set[str] = set()
        # Map tab id → loader method
        self._tab_loaders: dict[str, str] = {
            "tab-status":   "_load_status",
            "tab-commits":  "_load_commits",
            "tab-diff":     "_load_diff",
            "tab-branches": "_load_branches",
            "tab-remotes":  "_load_remotes",
            "tab-tags":     "_load_tags",
            "tab-tree":     "_load_tree",
        }

    def compose(self) -> ComposeResult:
        with TabbedContent(
            "📋 Status",
            "📝 Commits",
            "🔀 Diff",
            "🌿 Branches",
            "🌐 Remotes",
            "🏷️ Tags",
            "🌲 Tree",
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
                yield Static("", id="diff-footer", markup=True)

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

            # ── Tree Tab ──
            with TabPane("🌲 Tree", id="tab-tree"):
                yield Static(
                    "[dim italic]← Select a repository to view structure[/]",
                    id="tree-content",
                    markup=True,
                )

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
        """Switch to a new repository: reset loaded state, load the active tab only."""
        self._current_repo = repo_path
        self._current_info = repo_info
        self._loaded_tabs.clear()

        # Only load whichever tab is currently visible
        try:
            tc: TabbedContent = self.query_one(TabbedContent)
            active_id = str(tc.active) if tc.active else "tab-status"
        except Exception:
            active_id = "tab-status"

        self._load_tab(active_id)

    # -----------------------------------------------------------------
    # Lazy tab dispatch
    # -----------------------------------------------------------------

    def _load_tab(self, tab_id: str) -> None:
        """Load a single tab by its pane id (no-op if already loaded)."""
        if self._current_repo is None:
            return
        if tab_id in self._loaded_tabs:
            return
        method_name = self._tab_loaders.get(tab_id)
        if method_name is None:
            return
        method = getattr(self, method_name)
        if tab_id == "tab-status":
            method(self._current_repo, self._current_info)
        else:
            method(self._current_repo)
        self._loaded_tabs.add(tab_id)

    def on_tabbed_content_tab_activated(
        self, event: TabbedContent.TabActivated
    ) -> None:
        """Load data for a tab the first time it becomes visible."""
        self._load_tab(str(event.pane.id) if event.pane else "")

    # -----------------------------------------------------------------
    # Tab loaders
    # -----------------------------------------------------------------

    def _load_status(self, repo_path: Path, info: RepoInfo | None) -> None:
        """Populate the Status tab with summary header, file lists, and stashes."""
        fs = get_status(repo_path)
        stashes = get_stashes(repo_path)
        # ── Repo summary header as Rich Panel ──
        header = Text()
        header.append("  Path:   ", style="bold #7aa2f7")
        header.append(str(repo_path) + "\n", style="dim #565f89")
        if info:
            rel = relative_time(info.last_commit_ts)
            header.append("  Branch: ", style="bold #7aa2f7")
            header.append(info.branch + "\n", style="#bb9af7")
            header.append("  Commit: ", style="bold #7aa2f7")
            header.append(info.last_commit_msg, style="dim")
            header.append(f"  ({rel})\n", style="dim #565f89")
            header.append("  Stats:  ", style="bold #7aa2f7")
            header.append(str(info.total_commits), style="#9ece6a")
            header.append(" commits · ")
            header.append(str(info.contributor_count), style="#e0af68")
            n = info.contributor_count
            header.append(f" contributor{'s' if n != 1 else ''}")
        summary_panel = Panel(
            header,
            title=f"[bold #c0caf5] {repo_path.name} [/]",
            border_style="#3b4261",
            padding=(0, 0),
        )

        lines: list[str] = [""]

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
        content.update(Group(summary_panel, Text.from_markup("\n".join(lines))))

    def _load_commits(self, repo_path: Path) -> None:
        """Populate the Commits DataTable with stats."""
        table: DataTable = self.query_one("#commits-table", DataTable)
        table.clear()

        commits = get_commits(repo_path, self._commits_n)
        if not commits:
            table.add_row("—", "No commits", "", "", "", "")
            return

        for c in commits:
            # +/- with green/red colouring
            pm = Text()
            pm.append(f"+{c.insertions}", style="bold #9ece6a")
            pm.append(" ")
            pm.append(f"-{c.deletions}", style="bold #f7768e")
            table.add_row(
                c.short_hash,
                c.author,
                c.date,
                c.message[:60],
                str(c.files_changed),
                pm,
            )

    def _load_diff(self, repo_path: Path) -> None:
        """Populate the Diff tab with syntax-highlighted output and a line-count footer."""
        diff_text = get_diff(repo_path)
        content = self.query_one("#diff-content", Static)
        footer = self.query_one("#diff-footer", Static)
        content.remove_class("empty-message")

        if diff_text.startswith("No uncommitted"):
            content.update(f"[dim italic]{diff_text}[/]")
            footer.update("")
        else:
            line_count = len(diff_text.splitlines())
            syntax = Syntax(
                diff_text,
                "diff",
                theme="monokai",
                line_numbers=True,
                word_wrap=True,
            )
            content.update(syntax)
            footer.update(
                f"[dim #565f89]  {line_count} lines  ·  ↑↓ / PgUp PgDn to scroll[/]"
            )

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

    def _load_tree(self, repo_path: Path) -> None:
        """Populate the Tree tab with the repo's tracked file hierarchy."""
        content = self.query_one("#tree-content", Static)
        content.remove_class("empty-message")
        try:
            tree = get_file_tree(repo_path)
            content.update(tree)
        except Exception as exc:
            content.update(f"[dim italic]Error building tree: {exc}[/]")

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        """Handle Enter key on a branch item."""
        if (
            event.list_view.id == "branch-list"
            and isinstance(event.item, BranchListItem)
        ):
            self.post_message(
                self.BranchSwitchRequested(event.item.branch_info.name)
            )
