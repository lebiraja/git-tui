"""
tabs.py — Main panel tabs for GitPulse.

Provides Status, Commits, Diff, Branches, Remotes, Tags, and Tree tabs.

New in this version:
  • Interactive Status tab with stage/unstage/commit (s/u/a/c keys)
  • Full Diff tab: per-file picker on the left + scrollable syntax viewer on right
  • Tree tab: proper scrolling via ScrollableContainer
  • Commit modal dialog (with staged file list)
  • New branch modal dialog
  • Delete branch (d key in Branches tab)
  • View commit diff modal (Enter/d in Commits tab)
"""

from __future__ import annotations

from pathlib import Path

from rich.panel import Panel
from rich.syntax import Syntax
from rich.text import Text

from textual.app import ComposeResult
from textual.binding import Binding
from textual.message import Message
from textual.screen import ModalScreen
from textual.widget import Widget
from textual.widgets import (
    Button,
    DataTable,
    Input,
    ListItem,
    ListView,
    Static,
    TabbedContent,
    TabPane,
)
from textual.containers import Container, Horizontal, ScrollableContainer, Vertical

try:
    from gitpulse.git_ops import (
        get_status, get_commits, get_branches,
        get_stashes, get_remotes, get_tags, get_file_tree,
        get_changed_files, get_file_diff, get_commit_diff,
        stage_files, unstage_files, stage_all, unstage_all, commit_changes,
        create_branch, delete_branch,
        BranchInfo, RepoInfo,
    )
    from gitpulse.utils import relative_time
except ImportError:
    from git_ops import (  # type: ignore[no-redef]
        get_status, get_commits, get_branches,
        get_stashes, get_remotes, get_tags, get_file_tree,
        get_changed_files, get_file_diff, get_commit_diff,
        stage_files, unstage_files, stage_all, unstage_all, commit_changes,
        create_branch, delete_branch,
        BranchInfo, RepoInfo,
    )
    from utils import relative_time  # type: ignore[no-redef]


# ── Icons ──────────────────────────────────────────────────────────────────
_ICON_STAGED    = "✅"
_ICON_UNSTAGED  = "✏️ "
_ICON_UNTRACKED = "❓"
_ICON_STASH     = "📦"


# ===================================================================
# Modal: Commit dialog
# ===================================================================

class CommitModal(ModalScreen):
    """Modal dialog for composing and submitting a git commit."""

    DEFAULT_CSS = """
    CommitModal {
        align: center middle;
    }
    #commit-dialog {
        width: 64;
        height: auto;
        padding: 1 2;
        background: #1e2030;
        border: thick #7aa2f7;
    }
    #commit-title {
        text-style: bold;
        color: #7aa2f7;
        margin-bottom: 1;
        text-align: center;
        width: 100%;
        height: 1;
    }
    #commit-staged-info {
        color: #9ece6a;
        margin-bottom: 1;
        width: 100%;
        height: auto;
    }
    #commit-msg-input {
        width: 100%;
        margin-bottom: 1;
    }
    #commit-buttons {
        layout: horizontal;
        width: 100%;
        height: 3;
        align: center middle;
    }
    #btn-do-commit {
        margin: 0 1;
    }
    #btn-cancel-commit {
        margin: 0 1;
    }
    """

    def __init__(self, staged_files: list[str], **kwargs) -> None:
        super().__init__(**kwargs)
        self._staged_files = staged_files

    def compose(self) -> ComposeResult:
        with Container(id="commit-dialog"):
            yield Static(" 󰄬  Commit Changes", id="commit-title", markup=False)
            n = len(self._staged_files)
            if n == 0:
                info = "  No files staged. Use 's' or 'a' to stage first."
            else:
                names = ", ".join(self._staged_files[:4])
                extra = f" +{n - 4} more" if n > 4 else ""
                info = f"  Staged ({n}): {names}{extra}"
            yield Static(info, id="commit-staged-info", markup=False)
            yield Input(
                placeholder="Commit message  (Enter to commit · Esc to cancel)",
                id="commit-msg-input",
            )
            with Horizontal(id="commit-buttons"):
                yield Button("Commit", id="btn-do-commit", variant="success")
                yield Button("Cancel", id="btn-cancel-commit")

    def on_mount(self) -> None:
        self.query_one("#commit-msg-input", Input).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-do-commit":
            self._submit()
        else:
            self.dismiss(None)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "commit-msg-input":
            self._submit()

    def on_key(self, event) -> None:
        if event.key == "escape":
            self.dismiss(None)
            event.stop()

    def _submit(self) -> None:
        msg = self.query_one("#commit-msg-input", Input).value.strip()
        self.dismiss(msg or None)


# ===================================================================
# Modal: New branch dialog
# ===================================================================

class NewBranchModal(ModalScreen):
    """Modal dialog for creating a new git branch."""

    DEFAULT_CSS = """
    NewBranchModal {
        align: center middle;
    }
    #new-branch-dialog {
        width: 52;
        height: auto;
        padding: 1 2;
        background: #1e2030;
        border: thick #bb9af7;
    }
    #new-branch-title {
        text-style: bold;
        color: #bb9af7;
        margin-bottom: 1;
        text-align: center;
        width: 100%;
        height: 1;
    }
    #new-branch-input {
        width: 100%;
        margin-bottom: 1;
    }
    #new-branch-buttons {
        layout: horizontal;
        width: 100%;
        height: 3;
        align: center middle;
    }
    #btn-do-create {
        margin: 0 1;
    }
    #btn-cancel-branch {
        margin: 0 1;
    }
    """

    def compose(self) -> ComposeResult:
        with Container(id="new-branch-dialog"):
            yield Static("  New Branch", id="new-branch-title", markup=False)
            yield Input(
                placeholder="Branch name  (Enter to create · Esc to cancel)",
                id="new-branch-input",
            )
            with Horizontal(id="new-branch-buttons"):
                yield Button("Create", id="btn-do-create", variant="primary")
                yield Button("Cancel", id="btn-cancel-branch")

    def on_mount(self) -> None:
        self.query_one("#new-branch-input", Input).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-do-create":
            self._submit()
        else:
            self.dismiss(None)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "new-branch-input":
            self._submit()

    def on_key(self, event) -> None:
        if event.key == "escape":
            self.dismiss(None)
            event.stop()

    def _submit(self) -> None:
        name = self.query_one("#new-branch-input", Input).value.strip()
        self.dismiss(name or None)


# ===================================================================
# Modal: Commit diff viewer
# ===================================================================

class CommitDiffModal(ModalScreen):
    """Full-screen modal that shows the diff introduced by one commit."""

    BINDINGS = [Binding("escape,q", "close", "Close", show=True)]

    DEFAULT_CSS = """
    CommitDiffModal {
        align: center middle;
    }
    #cdiff-frame {
        width: 92%;
        height: 88%;
        background: #1e2030;
        border: thick #7aa2f7;
    }
    #cdiff-title {
        dock: top;
        height: 1;
        background: #24283b;
        color: #7aa2f7;
        text-style: bold;
        padding: 0 1;
    }
    #cdiff-scroll {
        width: 100%;
        height: 1fr;
    }
    #cdiff-body {
        padding: 0 1;
    }
    #cdiff-footer {
        dock: bottom;
        height: 1;
        background: #1e2030;
        color: #565f89;
        padding: 0 1;
        border-top: solid #3b4261;
    }
    """

    def __init__(self, short_hash: str, commit_msg: str, diff_text: str, **kwargs) -> None:
        super().__init__(**kwargs)
        self._hash = short_hash
        self._msg = commit_msg
        self._diff = diff_text

    def compose(self) -> ComposeResult:
        with Container(id="cdiff-frame"):
            yield Static(
                f" {self._hash} — {self._msg[:70]}",
                id="cdiff-title",
                markup=False,
            )
            with ScrollableContainer(id="cdiff-scroll"):
                if self._diff and not self._diff.startswith("No changes"):
                    body: object = Syntax(
                        self._diff, "diff", theme="monokai",
                        line_numbers=True, word_wrap=False,
                    )
                else:
                    body = f"[dim italic]{self._diff}[/]"
                yield Static(body, id="cdiff-body")
            lines = len(self._diff.splitlines())
            yield Static(
                f"  {lines} lines · ↑↓ PgUp PgDn scroll · Esc/q close",
                id="cdiff-footer",
                markup=False,
            )

    def action_close(self) -> None:
        self.dismiss()


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
# Diff file item (file picker in Diff tab)
# ===================================================================

class DiffFileItem(ListItem):
    """A file entry in the Diff tab's file picker."""

    DEFAULT_CSS = """
    DiffFileItem {
        height: 1;
        padding: 0 1;
    }
    """

    def __init__(self, filepath: str, status: str, **kwargs) -> None:
        super().__init__(**kwargs)
        self.filepath = filepath
        self.file_status = status  # "staged" | "unstaged" | "untracked"

    def compose(self) -> ComposeResult:
        if self.file_status == "staged":
            label = f"[bold #9ece6a]+ {self.filepath}[/]"
        elif self.file_status == "unstaged":
            label = f"[#e0af68]~ {self.filepath}[/]"
        else:
            label = f"[dim #f7768e]? {self.filepath}[/]"
        yield Static(label, markup=True)


# ===================================================================
# Status file item (interactive item for Status tab)
# ===================================================================

class StatusFileItem(ListItem):
    """An interactive file row in the Status tab."""

    DEFAULT_CSS = """
    StatusFileItem {
        height: 1;
        padding: 0 1;
    }
    """

    def __init__(self, filepath: str, status: str, **kwargs) -> None:
        super().__init__(**kwargs)
        self.filepath = filepath
        self.file_status = status  # "staged" | "unstaged" | "untracked"

    def compose(self) -> ComposeResult:
        if self.file_status == "staged":
            icon = _ICON_STAGED
            label = f"[bold #9ece6a]{icon} [staged]    {self.filepath}[/]"
        elif self.file_status == "unstaged":
            icon = _ICON_UNSTAGED
            label = f"[#e0af68]{icon} [unstaged]  {self.filepath}[/]"
        else:
            icon = _ICON_UNTRACKED
            label = f"[#f7768e]{icon} [untracked] {self.filepath}[/]"
        yield Static(label, markup=True)


# ===================================================================
# Main tabbed panel
# ===================================================================

class MainPanel(Widget):
    """
    Right-hand panel with seven tabs:
    Status, Commits, Diff, Branches, Remotes, Tags, Tree.
    """

    BINDINGS = [
        Binding("s",         "stage_file",    "Stage",       show=True),
        Binding("u",         "unstage_file",  "Unstage",     show=True),
        Binding("a",         "stage_all",     "Stage All",   show=True),
        Binding("shift+u",   "unstage_all",   "Unstage All", show=False),
        Binding("c",         "open_commit",   "Commit",      show=True),
        Binding("n",         "new_branch",    "New Branch",  show=True),
    ]

    # ── Messages ─────────────────────────────────────────────────────

    class BranchSwitchRequested(Message):
        def __init__(self, branch_name: str) -> None:
            super().__init__()
            self.branch_name = branch_name

    class ReloadRequested(Message):
        """Ask the app to reload the current repo's sidebar entry."""

    # ── Init ─────────────────────────────────────────────────────────

    def __init__(self, commits: int = 10, **kwargs) -> None:
        super().__init__(**kwargs)
        self._current_repo: Path | None = None
        self._current_info: RepoInfo | None = None
        self._commits_n = commits
        self._loaded_tabs: set[str] = set()
        self._tab_loaders: dict[str, str] = {
            "tab-status":   "_load_status",
            "tab-commits":  "_load_commits",
            "tab-diff":     "_load_diff",
            "tab-branches": "_load_branches",
            "tab-remotes":  "_load_remotes",
            "tab-tags":     "_load_tags",
            "tab-tree":     "_load_tree",
        }

    # ── Compose ──────────────────────────────────────────────────────

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
            # ── Status ──
            with TabPane("📋 Status", id="tab-status"):
                yield Static(
                    "[dim italic]← Select a repository[/]",
                    id="status-summary",
                    markup=True,
                )
                yield ListView(id="status-file-list")
                yield Static(
                    "[dim #565f89]  s=stage  u=unstage  a=stage-all  U=unstage-all  c=commit[/]",
                    id="status-hints",
                    markup=True,
                )

            # ── Commits ──
            with TabPane("📝 Commits", id="tab-commits"):
                yield DataTable(id="commits-table")
                yield Static(
                    "[dim #565f89]  Enter or d = view commit diff[/]",
                    id="commits-hints",
                    markup=True,
                )

            # ── Diff ──
            with TabPane("🔀 Diff", id="tab-diff"):
                with Horizontal(id="diff-layout"):
                    with Vertical(id="diff-file-panel"):
                        yield Static(
                            "[bold #7aa2f7] Files[/]",
                            id="diff-file-header",
                            markup=True,
                        )
                        yield ListView(id="diff-file-list")
                    with ScrollableContainer(id="diff-view-panel"):
                        yield Static(
                            "[dim italic]← Select a file[/]",
                            id="diff-content",
                            markup=True,
                        )
                yield Static(
                    "[dim #565f89]  + staged  ~ unstaged  ? untracked  ·  ↑↓ to navigate files[/]",
                    id="diff-footer",
                    markup=True,
                )

            # ── Branches ──
            with TabPane("🌿 Branches", id="tab-branches"):
                yield ListView(id="branch-list")
                yield Static(
                    "[dim #565f89]  Enter=switch branch  n=new branch  d=delete branch[/]",
                    id="branch-hints",
                    markup=True,
                )

            # ── Remotes ──
            with TabPane("🌐 Remotes", id="tab-remotes"):
                with ScrollableContainer(id="remotes-scroll"):
                    yield Static(
                        "[dim italic]← Select a repository to view remotes[/]",
                        id="remotes-content",
                        markup=True,
                    )

            # ── Tags ──
            with TabPane("🏷️ Tags", id="tab-tags"):
                yield DataTable(id="tags-table")

            # ── Tree ──
            with TabPane("🌲 Tree", id="tab-tree"):
                with ScrollableContainer(id="tree-scroll"):
                    yield Static(
                        "[dim italic]← Select a repository to view structure[/]",
                        id="tree-content",
                        markup=True,
                    )

    def on_mount(self) -> None:
        ct: DataTable = self.query_one("#commits-table", DataTable)
        ct.add_columns("Hash", "Author", "Date", "Message", "Files", "+/-")
        ct.cursor_type = "row"
        ct.zebra_stripes = True

        tt: DataTable = self.query_one("#tags-table", DataTable)
        tt.add_columns("Tag", "Date", "Tagger", "Message")
        tt.cursor_type = "row"
        tt.zebra_stripes = True

    # ── Public API ───────────────────────────────────────────────────

    def load_repo(self, repo_path: Path, repo_info: RepoInfo | None = None) -> None:
        self._current_repo = repo_path
        self._current_info = repo_info
        self._loaded_tabs.clear()
        try:
            tc: TabbedContent = self.query_one(TabbedContent)
            active_id = str(tc.active) if tc.active else "tab-status"
        except Exception:
            active_id = "tab-status"
        self._load_tab(active_id)

    # ── Tab dispatch ─────────────────────────────────────────────────

    def _load_tab(self, tab_id: str) -> None:
        if self._current_repo is None:
            return
        if tab_id in self._loaded_tabs:
            return
        method_name = self._tab_loaders.get(tab_id)
        if not method_name:
            return
        method = getattr(self, method_name)
        if tab_id == "tab-status":
            method(self._current_repo, self._current_info)
        else:
            method(self._current_repo)
        self._loaded_tabs.add(tab_id)

    def _reload_tab(self, tab_id: str) -> None:
        self._loaded_tabs.discard(tab_id)
        self._load_tab(tab_id)

    def on_tabbed_content_tab_activated(
        self, event: TabbedContent.TabActivated
    ) -> None:
        self._load_tab(str(event.pane.id) if event.pane else "")

    # ── Tab loaders ──────────────────────────────────────────────────

    def _load_status(self, repo_path: Path, info: RepoInfo | None) -> None:
        fs = get_status(repo_path)
        stashes = get_stashes(repo_path)

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
            n_contrib = info.contributor_count
            header.append(f" contributor{'s' if n_contrib != 1 else ''}")
        if stashes:
            header.append(f"\n  Stashes: ", style="bold #7aa2f7")
            header.append(str(len(stashes)), style="#7dcfff")
            header.append(f" ({', '.join(s.message[:30] for s in stashes[:2])})", style="dim")

        summary_panel = Panel(
            header,
            title=f"[bold #c0caf5] {repo_path.name} [/]",
            border_style="#3b4261",
            padding=(0, 0),
        )
        self.query_one("#status-summary", Static).update(summary_panel)

        file_list: ListView = self.query_one("#status-file-list", ListView)
        file_list.clear()

        if not fs.staged and not fs.unstaged and not fs.untracked:
            file_list.append(
                ListItem(Static(
                    "[bold #9ece6a]  ✨ Working tree clean — nothing to commit[/]",
                    markup=True,
                ))
            )
        else:
            if fs.staged:
                file_list.append(ListItem(Static(
                    f"[bold #9ece6a dim]── Staged ({len(fs.staged)}) ──────────────────[/]",
                    markup=True,
                )))
                for f in fs.staged:
                    file_list.append(StatusFileItem(f, "staged"))
            if fs.unstaged:
                file_list.append(ListItem(Static(
                    f"[bold #e0af68 dim]── Unstaged ({len(fs.unstaged)}) ────────────────[/]",
                    markup=True,
                )))
                for f in fs.unstaged:
                    file_list.append(StatusFileItem(f, "unstaged"))
            if fs.untracked:
                file_list.append(ListItem(Static(
                    f"[bold #f7768e dim]── Untracked ({len(fs.untracked)}) ───────────────[/]",
                    markup=True,
                )))
                for f in fs.untracked:
                    file_list.append(StatusFileItem(f, "untracked"))

    def _load_commits(self, repo_path: Path) -> None:
        table: DataTable = self.query_one("#commits-table", DataTable)
        table.clear()
        commits = get_commits(repo_path, self._commits_n)
        if not commits:
            table.add_row("—", "No commits", "", "", "", "")
            return
        for c in commits:
            pm = Text()
            pm.append(f"+{c.insertions}", style="bold #9ece6a")
            pm.append(" ")
            pm.append(f"-{c.deletions}", style="bold #f7768e")
            table.add_row(
                c.short_hash, c.author, c.date,
                c.message[:60], str(c.files_changed), pm,
            )

    def _load_diff(self, repo_path: Path) -> None:
        file_list: ListView = self.query_one("#diff-file-list", ListView)
        content: Static = self.query_one("#diff-content", Static)
        file_list.clear()
        content.update("[dim italic]← Select a file to view its diff[/]")

        changed = get_changed_files(repo_path)
        if not any(changed.values()):
            file_list.append(ListItem(Static(
                "[dim italic]  No uncommitted changes[/]", markup=True
            )))
            return

        for f in changed.get("staged", []):
            file_list.append(DiffFileItem(f, "staged"))
        for f in changed.get("unstaged", []):
            file_list.append(DiffFileItem(f, "unstaged"))
        for f in changed.get("untracked", []):
            file_list.append(DiffFileItem(f, "untracked"))

    def _load_branches(self, repo_path: Path) -> None:
        branch_list: ListView = self.query_one("#branch-list", ListView)
        branch_list.clear()
        branches = get_branches(repo_path)
        if not branches:
            branch_list.append(ListItem(
                Static("[dim italic]No branches found[/]", markup=True)
            ))
            return
        for b in branches:
            branch_list.append(BranchListItem(b))

    def _load_remotes(self, repo_path: Path) -> None:
        remotes = get_remotes(repo_path)
        lines: list[str] = []
        if not remotes:
            lines.append("[dim italic]No remotes configured[/]")
        else:
            for r in remotes:
                lines.append(f"[bold #7aa2f7]━━ {r.name} ━━[/]")
                lines.append(f"  [bold]URL:[/]   [dim]{r.url}[/]")
                if r.ahead or r.behind:
                    parts = []
                    if r.ahead:
                        parts.append(f"[bold #9ece6a]↑ {r.ahead} ahead[/]")
                    if r.behind:
                        parts.append(f"[bold #f7768e]↓ {r.behind} behind[/]")
                    lines.append(f"  [bold]Sync:[/]  {' · '.join(parts)}")
                else:
                    lines.append("  [bold]Sync:[/]  [#9ece6a]✓ Up to date[/]")
                lines.append("")
        self.query_one("#remotes-content", Static).update("\n".join(lines))

    def _load_tags(self, repo_path: Path) -> None:
        table: DataTable = self.query_one("#tags-table", DataTable)
        table.clear()
        tags = get_tags(repo_path)
        if not tags:
            table.add_row("—", "No tags", "", "")
            return
        for t in tags:
            table.add_row(t.name, t.date, t.tagger, t.message[:60])

    def _load_tree(self, repo_path: Path) -> None:
        content: Static = self.query_one("#tree-content", Static)
        try:
            tree = get_file_tree(repo_path)
            content.update(tree)
        except Exception as exc:
            content.update(f"[dim italic]Error building tree: {exc}[/]")

    # ── Diff: real-time preview on navigate ──────────────────────────

    def _show_file_diff(self, item: DiffFileItem) -> None:
        if self._current_repo is None:
            return
        if item.file_status == "untracked":
            diff_text = f"(new untracked file — not yet staged)\n\n{item.filepath}"
        else:
            staged = item.file_status == "staged"
            diff_text = get_file_diff(self._current_repo, item.filepath, staged=staged)
        content: Static = self.query_one("#diff-content", Static)
        if not diff_text or diff_text.startswith("(new"):
            content.update(f"[dim italic]{diff_text}[/]")
        else:
            content.update(
                Syntax(diff_text, "diff", theme="monokai",
                       line_numbers=True, word_wrap=False)
            )

    # ── Commit diff viewer ────────────────────────────────────────────

    def _open_commit_diff(self) -> None:
        if self._current_repo is None:
            return
        table: DataTable = self.query_one("#commits-table", DataTable)
        if table.cursor_row < 0:
            return
        try:
            row = table.get_row_at(table.cursor_row)
            short_hash = str(row[0])
            commit_msg = str(row[3])
        except Exception:
            return
        diff_text = get_commit_diff(self._current_repo, short_hash)
        self.app.push_screen(CommitDiffModal(short_hash, commit_msg, diff_text))

    # ── Key action helpers ────────────────────────────────────────────

    def _active_tab(self) -> str:
        try:
            tc: TabbedContent = self.query_one(TabbedContent)
            return str(tc.active) if tc.active else ""
        except Exception:
            return ""

    # ── Actions ──────────────────────────────────────────────────────

    def action_stage_file(self) -> None:
        if self._current_repo is None or self._active_tab() != "tab-status":
            return
        fl: ListView = self.query_one("#status-file-list", ListView)
        item = fl.highlighted_child
        if isinstance(item, StatusFileItem) and item.file_status in ("unstaged", "untracked"):
            msg = stage_files(self._current_repo, [item.filepath])
            self.app.notify(msg, timeout=2)
            self._reload_tab("tab-status")
            self._loaded_tabs.discard("tab-diff")

    def action_unstage_file(self) -> None:
        if self._current_repo is None or self._active_tab() != "tab-status":
            return
        fl: ListView = self.query_one("#status-file-list", ListView)
        item = fl.highlighted_child
        if isinstance(item, StatusFileItem) and item.file_status == "staged":
            msg = unstage_files(self._current_repo, [item.filepath])
            self.app.notify(msg, timeout=2)
            self._reload_tab("tab-status")
            self._loaded_tabs.discard("tab-diff")

    def action_stage_all(self) -> None:
        if self._current_repo is None:
            return
        msg = stage_all(self._current_repo)
        self.app.notify(msg, timeout=2)
        self._reload_tab("tab-status")
        self._loaded_tabs.discard("tab-diff")

    def action_unstage_all(self) -> None:
        if self._current_repo is None:
            return
        msg = unstage_all(self._current_repo)
        self.app.notify(msg, timeout=2)
        self._reload_tab("tab-status")
        self._loaded_tabs.discard("tab-diff")

    def action_open_commit(self) -> None:
        if self._current_repo is None:
            return
        changed = get_changed_files(self._current_repo)
        staged = changed.get("staged", [])

        async def _after_commit(message: str | None) -> None:
            if not message:
                return
            result = commit_changes(self._current_repo, message)
            self.app.notify(result, timeout=4)
            for tab in ("tab-status", "tab-commits", "tab-diff"):
                self._loaded_tabs.discard(tab)
            current_tab = self._active_tab()
            self._load_tab(current_tab or "tab-status")
            self.post_message(self.ReloadRequested())

        self.app.push_screen(CommitModal(staged_files=staged), _after_commit)

    def action_new_branch(self) -> None:
        if self._current_repo is None:
            return

        async def _after_create(name: str | None) -> None:
            if not name:
                return
            result = create_branch(self._current_repo, name)
            self.app.notify(result, timeout=3)
            self._reload_tab("tab-branches")
            self._loaded_tabs.discard("tab-status")
            self.post_message(self.ReloadRequested())

        self.app.push_screen(NewBranchModal(), _after_create)


    def _delete_selected_branch(self) -> None:
        if self._current_repo is None:
            return
        bl: ListView = self.query_one("#branch-list", ListView)
        item = bl.highlighted_child
        if not isinstance(item, BranchListItem):
            return
        if item.branch_info.is_current:
            self.app.notify(
                "Cannot delete the currently checked-out branch.",
                severity="warning", timeout=3,
            )
            return
        result = delete_branch(self._current_repo, item.branch_info.name)
        self.app.notify(result, timeout=3)
        self._reload_tab("tab-branches")
        self.post_message(self.ReloadRequested())

    # ── Events ───────────────────────────────────────────────────────

    def on_list_view_highlighted(self, event: ListView.Highlighted) -> None:
        """Real-time diff preview when navigating the Diff tab file list."""
        if (
            event.list_view.id == "diff-file-list"
            and isinstance(event.item, DiffFileItem)
        ):
            self._show_file_diff(event.item)

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        """Enter on a branch → switch; Enter on Diff file → show diff."""
        if (
            event.list_view.id == "branch-list"
            and isinstance(event.item, BranchListItem)
        ):
            self.post_message(
                self.BranchSwitchRequested(event.item.branch_info.name)
            )

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Enter on a commit row → open commit diff modal."""
        if event.data_table.id == "commits-table":
            self._open_commit_diff()

    def on_key(self, event) -> None:
        """Route 'd' key depending on active tab."""
        if event.key == "d":
            tab = self._active_tab()
            if tab == "tab-branches":
                self._delete_selected_branch()
                event.stop()
            elif tab == "tab-commits":
                self._open_commit_diff()
                event.stop()
