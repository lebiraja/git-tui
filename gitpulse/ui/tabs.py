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

import re
from pathlib import Path

from rich.syntax import Syntax
from rich.text import Text

from textual.app import ComposeResult
from textual.binding import Binding
from textual.message import Message
from textual.screen import ModalScreen
from textual.widget import Widget
from textual.widgets import (
    Button,
    ContentSwitcher,
    DataTable,
    Input,
    ListItem,
    ListView,
    Static,
    TabbedContent,
    TabPane,
    Tree,
)
from textual.containers import Container, Horizontal, ScrollableContainer, Vertical

try:
    from gitpulse.git_ops import (
        get_status, get_commits, get_branches,
        get_stashes, get_remotes, get_tags, get_file_tree,
        get_changed_files, get_file_diff, get_commit_diff,
        stage_files, unstage_files, stage_all, unstage_all, commit_changes,
        create_branch, delete_branch,
        git_fetch, git_pull, git_push,
        stash_create, stash_pop,
        get_commit_graph, get_file_contents, get_tracked_files,
        is_dirty, classify_error,
        BranchInfo, RepoInfo,
    )
    from gitpulse.utils import relative_time
    from gitpulse.ui.summary_cards import SummaryCards
    from gitpulse.ui.confirm_modal import ConfirmModal, TypedConfirmModal
except ImportError:
    from git_ops import (  # type: ignore[no-redef]
        get_status, get_commits, get_branches,
        get_stashes, get_remotes, get_tags, get_file_tree,
        get_changed_files, get_file_diff, get_commit_diff,
        stage_files, unstage_files, stage_all, unstage_all, commit_changes,
        create_branch, delete_branch,
        git_fetch, git_pull, git_push,
        stash_create, stash_pop,
        get_commit_graph, get_file_contents, get_tracked_files,
        is_dirty, classify_error,
        BranchInfo, RepoInfo,
    )
    from utils import relative_time  # type: ignore[no-redef]
    from ui.summary_cards import SummaryCards  # type: ignore[no-redef]
    from ui.confirm_modal import ConfirmModal, TypedConfirmModal  # type: ignore[no-redef]


def _record_app_error(app, detail: str) -> None:
    """Append a raw error detail to the app's ring buffer, if present."""
    log = getattr(app, "_error_log", None)
    if log is None:
        return
    try:
        log.append(detail)
        if len(log) > 50:
            del log[0 : len(log) - 50]
    except Exception:
        pass


# ===================================================================
# Modal: Commit dialog
# ===================================================================

class CommitModal(ModalScreen):
    """Three-pane commit dialog.

    Left column: Staged / Unstaged / Untracked file lists.
    Right column: commit message input + action buttons.

    Keys:
      Space            toggle stage / unstage on highlighted file
      Tab / Shift+Tab  cycle focus between panes and the message input
      Ctrl+Enter       commit (also Enter from message input)
      Esc              cancel
    """

    BINDINGS = [
        Binding("escape", "cancel", "Cancel", show=True),
        Binding("ctrl+j", "commit", "Commit", show=True),  # Ctrl+Enter on most terminals
        Binding("ctrl+s", "commit", "Commit", show=False),
        Binding("space", "toggle_stage", "Stage/Unstage", show=True),
    ]

    DEFAULT_CSS = """
    CommitModal { align: center middle; }
    #commit-frame {
        width: 110;
        max-width: 95%;
        height: 32;
        max-height: 90%;
        padding: 1 2;
        background: #111827;
        border: round #8b5cf6;
    }
    #commit-title {
        width: 100%;
        height: 1;
        text-style: bold;
        color: #8b5cf6;
        margin-bottom: 1;
    }
    #commit-body { width: 100%; height: 1fr; }
    #commit-left  { width: 1fr; height: 100%; padding-right: 1; }
    #commit-right { width: 50; height: 100%; padding-left: 1; border-left: solid #1f2937; }
    #commit-sub-tabs { height: 1fr; }
    .commit-list { height: 1fr; background: #0b0f14; border: solid #1f2937; }
    #commit-msg-input { width: 100%; margin-bottom: 1; }
    #commit-error { width: 100%; height: auto; color: #ef4444; margin-bottom: 1; }
    #commit-help  { width: 100%; height: auto; color: #6b7280; margin-bottom: 1; }
    #commit-btns  { width: 100%; height: 3; align: right middle; }
    #commit-btns Button { margin: 0 0 0 1; min-width: 12; }
    """

    def __init__(self, repo_path: Path, **kwargs) -> None:
        super().__init__(**kwargs)
        self._repo_path = repo_path
        self._fs = get_status(repo_path)

    def compose(self) -> ComposeResult:
        with Container(id="commit-frame"):
            yield Static(f"Commit — {self._repo_path.name}", id="commit-title", markup=False)
            with Horizontal(id="commit-body"):
                with Vertical(id="commit-left"):
                    with TabbedContent(id="commit-sub-tabs"):
                        with TabPane(f"Staged ({len(self._fs.staged)})", id="ct-staged"):
                            yield ListView(id="cm-staged-list", classes="commit-list")
                        with TabPane(f"Unstaged ({len(self._fs.unstaged)})", id="ct-unstaged"):
                            yield ListView(id="cm-unstaged-list", classes="commit-list")
                        with TabPane(f"Untracked ({len(self._fs.untracked)})", id="ct-untracked"):
                            yield ListView(id="cm-untracked-list", classes="commit-list")
                with Vertical(id="commit-right"):
                    yield Static(
                        "Space = stage/unstage  ·  Ctrl+Enter = commit  ·  Esc = cancel",
                        id="commit-help", markup=False,
                    )
                    yield Static("", id="commit-error", markup=False)
                    yield Input(
                        placeholder="Commit message…",
                        id="commit-msg-input",
                    )
                    with Horizontal(id="commit-btns"):
                        yield Button("Cancel", id="cm-cancel")
                        yield Button("Commit", id="cm-commit", variant="success")

    def on_mount(self) -> None:
        self._refill()
        self.query_one("#commit-msg-input", Input).focus()

    def _refill(self) -> None:
        self._fs = get_status(self._repo_path)
        for tab_id, files, kind, empty in (
            ("ct-staged",    self._fs.staged,    "staged",    "No files staged"),
            ("ct-unstaged",  self._fs.unstaged,  "unstaged",  "No unstaged changes"),
            ("ct-untracked", self._fs.untracked, "untracked", "No untracked files"),
        ):
            try:
                pane = self.query_one(f"#{tab_id}", TabPane)
                pane.label = f"{kind.capitalize()} ({len(files)})"
            except Exception:
                pass
            list_id = {
                "ct-staged": "#cm-staged-list",
                "ct-unstaged": "#cm-unstaged-list",
                "ct-untracked": "#cm-untracked-list",
            }[tab_id]
            lv = self.query_one(list_id, ListView)
            lv.clear()
            if not files:
                lv.append(ListItem(Static(f"  [dim #6b7280]{empty}[/]", markup=True)))
                continue
            for f in files:
                lv.append(StatusFileItem(f, kind))

    def _active_list_and_kind(self) -> tuple[ListView | None, str]:
        try:
            tc = self.query_one("#commit-sub-tabs", TabbedContent)
            active = str(tc.active or "ct-staged")
        except Exception:
            return None, ""
        mapping = {
            "ct-staged":    ("#cm-staged-list",    "staged"),
            "ct-unstaged":  ("#cm-unstaged-list",  "unstaged"),
            "ct-untracked": ("#cm-untracked-list", "untracked"),
        }
        list_id, kind = mapping.get(active, ("#cm-staged-list", "staged"))
        try:
            return self.query_one(list_id, ListView), kind
        except Exception:
            return None, kind

    def action_toggle_stage(self) -> None:
        lv, kind = self._active_list_and_kind()
        if lv is None:
            return
        item = lv.highlighted_child
        if not isinstance(item, StatusFileItem):
            return
        if kind == "staged":
            unstage_files(self._repo_path, [item.filepath])
        else:
            stage_files(self._repo_path, [item.filepath])
        self._refill()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "cm-commit":
            self._submit()
        else:
            self.dismiss(None)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "commit-msg-input":
            self._submit()

    def action_cancel(self) -> None:
        self.dismiss(None)

    def action_commit(self) -> None:
        self._submit()

    def _submit(self) -> None:
        msg = self.query_one("#commit-msg-input", Input).value.strip()
        err = self.query_one("#commit-error", Static)
        if not msg:
            err.update("  ✗ Commit message cannot be empty")
            return
        if not self._fs.staged:
            err.update("  ✗ No staged files — Space on a file to stage it")
            return
        self.dismiss(msg)


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
        background: #111827;
        border: solid #8b5cf6;
    }
    #new-branch-title {
        text-style: bold;
        color: #8b5cf6;
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

    def __init__(self, existing: list[str] | None = None, **kwargs) -> None:
        super().__init__(**kwargs)
        self._existing = set(existing or [])

    def compose(self) -> ComposeResult:
        with Container(id="new-branch-dialog"):
            yield Static("New Branch", id="new-branch-title", markup=False)
            yield Static("", id="new-branch-error", markup=False)
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
        err = self.query_one("#new-branch-error", Static)
        if not name:
            err.update("  ✗ Branch name cannot be empty")
            return
        # git ref name rules (subset of check-ref-format)
        invalid = re.search(r"[\s~^:?*\[\\]|\.\.|@\{|//", name) or name.startswith((".", "/", "-")) or name.endswith((".", "/", ".lock"))
        if invalid:
            err.update("  ✗ Invalid branch name (no spaces, ~ ^ : ? * [ \\ .. //)")
            return
        if name in self._existing:
            err.update(f"  ✗ Branch '{name}' already exists")
            return
        self.dismiss(name)


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
        background: #111827;
        border: solid #8b5cf6;
    }
    #cdiff-title {
        dock: top;
        height: 1;
        background: #1f2937;
        color: #8b5cf6;
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
        background: #111827;
        color: #6b7280;
        padding: 0 1;
        border-top: solid #1f2937;
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
# Modal: Stash dialog
# ===================================================================

class StashModal(ModalScreen):
    """Modal dialog for creating a new git stash."""

    DEFAULT_CSS = """
    StashModal {
        align: center middle;
    }
    #stash-dialog {
        width: 56;
        height: auto;
        padding: 1 2;
        background: #111827;
        border: solid #f59e0b;
    }
    #stash-title {
        text-style: bold;
        color: #f59e0b;
        margin-bottom: 1;
        text-align: center;
        width: 100%;
        height: 1;
    }
    #stash-msg-input {
        width: 100%;
        margin-bottom: 1;
    }
    #stash-buttons {
        layout: horizontal;
        width: 100%;
        height: 3;
        align: center middle;
    }
    #btn-do-stash { margin: 0 1; }
    #btn-cancel-stash { margin: 0 1; }
    """

    def compose(self) -> ComposeResult:
        with Container(id="stash-dialog"):
            yield Static("  Stash Changes", id="stash-title", markup=False)
            yield Input(
                placeholder="Stash message  (optional · Enter to stash · Esc to cancel)",
                id="stash-msg-input",
            )
            with Horizontal(id="stash-buttons"):
                yield Button("Stash", id="btn-do-stash", variant="warning")
                yield Button("Cancel", id="btn-cancel-stash")

    def on_mount(self) -> None:
        self.query_one("#stash-msg-input", Input).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-do-stash":
            self._submit()
        else:
            self.dismiss(None)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "stash-msg-input":
            self._submit()

    def on_key(self, event) -> None:
        if event.key == "escape":
            self.dismiss(None)
            event.stop()

    def _submit(self) -> None:
        msg = self.query_one("#stash-msg-input", Input).value.strip()
        self.dismiss(msg)  # Empty string = no message, still valid


# ===================================================================
# Modal: File preview
# ===================================================================

class FilePreviewModal(ModalScreen):
    """Full-screen modal showing the content of a file with syntax highlighting."""

    BINDINGS = [Binding("escape,q", "close", "Close", show=True)]

    DEFAULT_CSS = """
    FilePreviewModal {
        align: center middle;
    }
    #fpreview-frame {
        width: 92%;
        height: 88%;
        background: #111827;
        border: solid #22c55e;
    }
    #fpreview-title {
        dock: top;
        height: 1;
        background: #1f2937;
        color: #22c55e;
        text-style: bold;
        padding: 0 1;
    }
    #fpreview-scroll {
        width: 100%;
        height: 1fr;
    }
    #fpreview-body {
        padding: 0 1;
    }
    #fpreview-footer {
        dock: bottom;
        height: 1;
        background: #111827;
        color: #6b7280;
        padding: 0 1;
        border-top: solid #1f2937;
    }
    """

    def __init__(self, filepath: str, content: str, **kwargs) -> None:
        super().__init__(**kwargs)
        self._filepath = filepath
        self._content = content

    def compose(self) -> ComposeResult:
        # Detect language from extension for syntax highlighting
        ext = self._filepath.rsplit(".", 1)[-1].lower() if "." in self._filepath else "text"
        _EXT_MAP = {
            "py": "python", "js": "javascript", "ts": "typescript",
            "rs": "rust", "go": "go", "c": "c", "cpp": "cpp",
            "java": "java", "sh": "bash", "bash": "bash",
            "yaml": "yaml", "yml": "yaml", "toml": "toml",
            "json": "json", "md": "markdown", "html": "html",
            "css": "css", "tcss": "css", "sql": "sql",
            "rb": "ruby", "php": "php",
        }
        lang = _EXT_MAP.get(ext, "text")
        lines = len(self._content.splitlines())

        with Container(id="fpreview-frame"):
            yield Static(
                f"  {self._filepath}",
                id="fpreview-title",
                markup=False,
            )
            with ScrollableContainer(id="fpreview-scroll"):
                if self._content.startswith("Error reading"):
                    body: object = f"[dim italic]{self._content}[/]"
                else:
                    body = Syntax(
                        self._content, lang, theme="monokai",
                        line_numbers=True, word_wrap=False,
                    )
                yield Static(body, id="fpreview-body")
            yield Static(
                f"  {lines} lines · lang={lang} · ↑↓ PgUp PgDn scroll · Esc/q close",
                id="fpreview-footer",
                markup=False,
            )

    def action_close(self) -> None:
        self.dismiss()


# ===================================================================
# Branch list item
# ===================================================================

class BranchListItem(ListItem):
    """A two-line branch row in the Branches tab: name + tip-commit context."""

    DEFAULT_CSS = """
    BranchListItem {
        height: 2;
        padding: 0 1;
        border-bottom: solid #1f2937;
    }
    """

    def __init__(self, branch_info: BranchInfo, **kwargs) -> None:
        super().__init__(**kwargs)
        self.branch_info = branch_info

    def compose(self) -> ComposeResult:
        b = self.branch_info
        # Line 1 — marker + name + tags
        if b.is_current:
            line1 = f"[bold #22c55e]● {b.name}[/]  [dim italic](current)[/]"
        else:
            line1 = f"[#8b5cf6]  {b.name}[/]"
        tags = []
        if b.has_upstream:
            tags.append("[#6b7280]⇅ tracked[/]")
        else:
            tags.append("[#6b7280]local-only[/]")
        line1 += "   " + " ".join(tags)

        # Line 2 — tip commit subject + relative time (muted)
        rel = relative_time(b.last_commit_ts) if b.last_commit_ts else ""
        msg = b.last_commit_msg[:48] + ("…" if len(b.last_commit_msg) > 48 else "")
        if msg:
            line2 = f"     [#6b7280]{msg}[/]  [dim]· {rel}[/]"
        else:
            line2 = "     [dim #6b7280]no commits[/]"

        yield Static(f"{line1}\n{line2}", markup=True)


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
        self.filepath = filepath
        self.file_status = status  # "staged" | "unstaged" | "untracked"
        t = Text(overflow="ellipsis", no_wrap=True)
        if status == "staged":
            t.append(f"+ {filepath}", style="bold #22c55e")
        elif status == "unstaged":
            t.append(f"~ {filepath}", style="#f59e0b")
        else:
            t.append(f"? {filepath}", style="dim #ef4444")
        super().__init__(Static(t), **kwargs)


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
        self.filepath = filepath
        self.file_status = status  # "staged" | "unstaged" | "untracked"
        t = Text(overflow="ellipsis", no_wrap=True)
        if status == "staged":
            t.append("+ ", style="bold #22c55e")
            t.append(filepath, style="#d1d5db")
        elif status == "unstaged":
            t.append("~ ", style="bold #f59e0b")
            t.append(filepath, style="#d1d5db")
        else:
            t.append("? ", style="bold #ef4444")
            t.append(filepath, style="#d1d5db")
        super().__init__(Static(t), **kwargs)


# ===================================================================
# Main tabbed panel
# ===================================================================

# ── Tab data fetchers (run in worker threads — must NOT touch Textual widgets) ──

def _fetch_status(path, info, commits_n):
    fs = get_status(path)
    stashes = get_stashes(path)
    try:
        file_tree = get_file_tree(path)
    except Exception:
        file_tree = None
    return {
        "info": info,
        "fs": fs,
        "stashes": stashes,
        "file_tree": file_tree,
        "recent_commits": get_commits(path, 6),
        "remotes": get_remotes(path),
    }


def _fetch_commits(path, info, commits_n):
    return {
        "commits": get_commits(path, commits_n),
        "graph": get_commit_graph(path, max(commits_n, 40)),
    }


def _fetch_diff(path, info, commits_n):
    return {"changed": get_changed_files(path)}


def _fetch_branches(path, info, commits_n):
    return {"branches": get_branches(path)}


def _fetch_remotes(path, info, commits_n):
    return {"remotes": get_remotes(path)}


def _fetch_tags(path, info, commits_n):
    return {"tags": get_tags(path)}


def _fetch_tree(path, info, commits_n):
    return {"files": get_tracked_files(path)}


_TAB_FETCHERS = {
    "status":   _fetch_status,
    "commits":  _fetch_commits,
    "diff":     _fetch_diff,
    "branches": _fetch_branches,
    "remotes":  _fetch_remotes,
    "tags":     _fetch_tags,
    "tree":     _fetch_tree,
}


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
        Binding("z",         "stash_create",  "Stash",       show=False),
        Binding("shift+z",   "stash_pop",     "Pop Stash",   show=False),
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
        # Per-tab monotonic token so stale worker results never overwrite
        # the UI when the user has switched repo/tab in the meantime.
        self._tab_token: dict[str, int] = {}

    # ── Compose ──────────────────────────────────────────────────────

    def compose(self) -> ComposeResult:
        with ContentSwitcher(initial="pane-status", id="main-content"):
            # ── Status ──
            with Vertical(id="pane-status", classes="content-pane"):
                yield Static(
                    "[#6b7280]Select a repository[/]",
                    id="repo-header",
                    markup=True,
                )
                yield SummaryCards(id="summary-cards")
                with Horizontal(id="status-body"):
                    with Vertical(id="status-workspace"):
                        with TabbedContent(id="workspace-tabs"):
                            with TabPane("Staged", id="ws-staged"):
                                yield ListView(id="staged-list")
                            with TabPane("Unstaged", id="ws-unstaged"):
                                yield ListView(id="unstaged-list")
                            with TabPane("Untracked", id="ws-untracked"):
                                yield ListView(id="untracked-list")
                            with TabPane("Stashes", id="ws-stashes"):
                                yield ListView(id="stashes-list")
                    with Vertical(id="status-rightbar"):
                        with ScrollableContainer(classes="panel", id="panel-tree"):
                            yield Static("", id="status-tree", markup=True)
                        with ScrollableContainer(classes="panel", id="panel-commits"):
                            yield Static("", id="status-commits", markup=True)
                        with ScrollableContainer(classes="panel", id="panel-remotes"):
                            yield Static("", id="status-remotes", markup=True)

            # ── Commits ──
            with Vertical(id="pane-commits", classes="content-pane"):
                with Vertical(id="commits-layout"):
                    with ScrollableContainer(id="commits-graph-scroll"):
                        yield Static(
                            "[#6b7280]Select a repository to view commit graph[/]",
                            id="commits-graph",
                            markup=True,
                        )
                    yield DataTable(id="commits-table")
                yield Static(
                    "[#6b7280]  Enter or d = view commit diff[/]",
                    id="commits-hints",
                    markup=True,
                )

            # ── Diff ──
            with Vertical(id="pane-diff", classes="content-pane"):
                with Horizontal(id="diff-layout"):
                    with Vertical(id="diff-file-panel"):
                        yield Static(
                            "[bold #6b7280] Files[/]",
                            id="diff-file-header",
                            markup=True,
                        )
                        yield ListView(id="diff-file-list")
                    with ScrollableContainer(id="diff-view-panel"):
                        yield Static(
                            "[#6b7280]Select a file from the left panel to view its diff[/]",
                            id="diff-content",
                            markup=True,
                        )
                yield Static(
                    "[#6b7280]  + staged   ~ unstaged   ? untracked   ·   ↑↓ to navigate files[/]",
                    id="diff-footer",
                    markup=True,
                )

            # ── Branches ──
            with Vertical(id="pane-branches", classes="content-pane"):
                yield Static(
                    "[#6b7280]Local branches[/]",
                    id="branch-header",
                    markup=True,
                )
                yield ListView(id="branch-list")
                yield Static(
                    "[#6b7280]  Enter switch branch   n new branch   d delete branch[/]",
                    id="branch-hints",
                    markup=True,
                )

            # ── Remotes ──
            with Vertical(id="pane-remotes", classes="content-pane"):
                with ScrollableContainer(id="remotes-scroll"):
                    yield Static(
                        "[#6b7280]Select a repository to view remote configuration[/]",
                        id="remotes-content",
                        markup=True,
                    )
                yield Static(
                    "[#6b7280]  f fetch   p pull   P push[/]",
                    id="remotes-hints",
                    markup=True,
                )

            # ── Tags ──
            with Vertical(id="pane-tags", classes="content-pane"):
                yield Static(
                    "[#6b7280]Tags[/]",
                    id="tags-header",
                    markup=True,
                )
                yield DataTable(id="tags-table")

            # ── Tree ──
            with Vertical(id="pane-tree", classes="content-pane"):
                yield Tree("Select a repository to browse files", id="tree-widget")
                yield Static(
                    "[#6b7280]  ↑↓ navigate   Enter = preview file[/]",
                    id="tree-hints",
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

        for panel_id, title in (
            ("#panel-tree", "FILE TREE"),
            ("#panel-commits", "RECENT COMMITS"),
            ("#panel-remotes", "REMOTE SUMMARY"),
        ):
            try:
                self.query_one(panel_id).border_title = title
            except Exception:
                pass

    # ── Public API ───────────────────────────────────────────────────

    def load_repo(self, repo_path: Path, repo_info: RepoInfo | None = None) -> None:
        self._current_repo = repo_path
        self._current_info = repo_info
        self._loaded_tabs.clear()
        # Bump every tab's token so any in-flight workers for the previous
        # repo are discarded when they complete.
        for k in list(self._tab_token.keys()):
            self._tab_token[k] += 1
        self._load_tab(self._active_tab())

    def show_tab(self, tab_id: str) -> None:
        """Switch the visible pane (driven by AppHeader.TabChanged)."""
        try:
            cs: ContentSwitcher = self.query_one("#main-content", ContentSwitcher)
            cs.current = f"pane-{tab_id}"
        except Exception:
            return
        self._load_tab(tab_id)

    def _active_tab(self) -> str:
        """Return the active tab id ('status', 'commits', …)."""
        try:
            cs: ContentSwitcher = self.query_one("#main-content", ContentSwitcher)
            current = cs.current or "pane-status"
            return current.removeprefix("pane-")
        except Exception:
            return "status"

    # ── Tab dispatch ─────────────────────────────────────────────────

    def _load_tab(self, tab_id: str) -> None:
        """Kick off (or short-circuit) loading of a tab in a worker thread."""
        if self._current_repo is None:
            return
        if tab_id in self._loaded_tabs:
            return

        fetcher = _TAB_FETCHERS.get(tab_id)
        if fetcher is None:
            return

        # Paint skeleton immediately so the user sees a response.
        self._paint_skeleton(tab_id)
        # Mark in-progress so we don't kick off a duplicate worker.
        self._loaded_tabs.add(tab_id)

        path = self._current_repo
        info = self._current_info
        commits_n = self._commits_n
        token = self._tab_token.get(tab_id, 0) + 1
        self._tab_token[tab_id] = token

        def _runner():
            try:
                data = fetcher(path, info, commits_n)
                return ("ok", tab_id, token, path, data)
            except Exception as exc:
                return ("err", tab_id, token, path, exc)

        self.run_worker(
            _runner, thread=True, group=f"tabload:{tab_id}", exclusive=True,
        )

    def _reload_tab(self, tab_id: str) -> None:
        self._loaded_tabs.discard(tab_id)
        self._load_tab(tab_id)

    # ── Skeletons (instant paint while worker fetches) ──────────────

    def _paint_skeleton(self, tab_id: str) -> None:
        try:
            if tab_id == "status":
                self.query_one("#repo-header", Static).update(
                    "[#6b7280]Loading repository…[/]"
                )
                for sid in ("#status-tree", "#status-commits", "#status-remotes"):
                    self.query_one(sid, Static).update("[dim #6b7280]loading…[/]")
                for lid, label in (
                    ("#staged-list", "loading…"),
                    ("#unstaged-list", "loading…"),
                    ("#untracked-list", "loading…"),
                    ("#stashes-list", "loading…"),
                ):
                    lv = self.query_one(lid, ListView)
                    lv.clear()
                    lv.append(ListItem(Static(f"[dim #6b7280]  {label}[/]", markup=True)))
            elif tab_id == "commits":
                self.query_one("#commits-table", DataTable).clear()
                self.query_one("#commits-graph", Static).update("[dim #6b7280]loading commit graph…[/]")
            elif tab_id == "diff":
                fl = self.query_one("#diff-file-list", ListView)
                fl.clear()
                fl.append(ListItem(Static("[dim #6b7280]  loading…[/]", markup=True)))
                self.query_one("#diff-content", Static).update("[dim #6b7280]loading…[/]")
            elif tab_id == "branches":
                bl = self.query_one("#branch-list", ListView)
                bl.clear()
                bl.append(ListItem(Static("[dim #6b7280]  loading branches…[/]", markup=True)))
            elif tab_id == "remotes":
                self.query_one("#remotes-content", Static).update("[dim #6b7280]loading remotes…[/]")
            elif tab_id == "tags":
                t = self.query_one("#tags-table", DataTable)
                t.clear()
            elif tab_id == "tree":
                tw = self.query_one("#tree-widget", Tree)
                tw.clear()
                tw.root.label = "loading…"
        except Exception:
            pass

    # ── Worker result dispatch ──────────────────────────────────────

    def _on_tab_result(self, tab_id: str, token: int, path: Path, status: str, data) -> None:
        """Apply (or discard) a tab worker's result on the UI thread."""
        # Discard stale results (user switched repo / re-requested).
        if self._current_repo != path:
            return
        if self._tab_token.get(tab_id) != token:
            return
        if status == "err":
            hint, detail = classify_error(data)
            self.app.notify(f"{tab_id}: {hint}", severity="error", timeout=5)
            _record_app_error(self.app, detail)
            # Allow a retry next time the tab is visited.
            self._loaded_tabs.discard(tab_id)
            return
        applier = getattr(self, f"_apply_{tab_id}", None)
        if applier is None:
            return
        try:
            applier(path, data)
        except Exception as exc:
            self.app.notify(f"render error: {exc}", severity="error", timeout=4)

    # ── Tab loaders ──────────────────────────────────────────────────

    def _apply_status(self, repo_path: Path, data: dict) -> None:
        info = data["info"]
        fs = data["fs"]
        stashes = data["stashes"]

        rel = relative_time(info.last_commit_ts) if info else ""
        self.query_one("#repo-header", Static).update(
            f"[bold #d1d5db]{repo_path.name}[/]   "
            f"[#6b7280]Path:[/] [#d1d5db]{repo_path}[/]   "
            f"[#6b7280]updated {rel}[/]"
        )

        self.query_one("#summary-cards", SummaryCards).update_cards(info, stashes)

        self._fill_ws_list("#staged-list", fs.staged, "staged", "No changes staged")
        self._fill_ws_list("#unstaged-list", fs.unstaged, "unstaged", "No unstaged changes")
        self._fill_ws_list("#untracked-list", fs.untracked, "untracked", "No untracked files")
        self._fill_stash_list(stashes)

        # Right-hand panels — use the data already fetched in the worker.
        self._apply_status_panels(data)

    def _empty_row(self, message: str) -> ListItem:
        """Build a centered empty-state row for an empty workspace list."""
        item = ListItem(Static(
            f"[#22c55e]✓[/]\n[#d1d5db]{message}[/]\n"
            f"[#6b7280]Working tree is clean[/]",
            markup=True,
        ))
        item.add_class("empty-row")
        return item

    def _fill_ws_list(
        self, list_id: str, files: list[str], status: str, empty_msg: str
    ) -> None:
        lv: ListView = self.query_one(list_id, ListView)
        lv.clear()
        if not files:
            lv.append(self._empty_row(empty_msg))
            return
        for f in files:
            lv.append(StatusFileItem(f, status))

    def _fill_stash_list(self, stashes: list) -> None:
        lv: ListView = self.query_one("#stashes-list", ListView)
        lv.clear()
        if not stashes:
            lv.append(self._empty_row("No stashes"))
            return
        for s in stashes:
            t = Text(overflow="ellipsis", no_wrap=True)
            t.append(f"stash@{{{s.index}}} ", style="bold #8b5cf6")
            t.append(s.message, style="#d1d5db")
            lv.append(ListItem(Static(t)))

    def _apply_status_panels(self, data: dict) -> None:
        """Populate the three right-hand panels from pre-fetched data."""
        tree = data.get("file_tree") or "[#6b7280]No tracked files[/]"
        self.query_one("#status-tree", Static).update(tree)

        commits = data.get("recent_commits") or []
        if commits:
            lines: list[str] = []
            for c in commits:
                author = c.author.split("<")[0].strip()
                lines.append(
                    f"[#d1d5db]{c.message[:34]}[/]\n"
                    f"[#6b7280]{c.date}  ·  {author}  [/]"
                    f"[#8b5cf6]{c.short_hash}[/]"
                )
            self.query_one("#status-commits", Static).update("\n".join(lines))
        else:
            self.query_one("#status-commits", Static).update("[#6b7280]No commits[/]")

        remotes = data.get("remotes") or []
        if remotes:
            lines = []
            for r in remotes:
                lines.append(
                    f"[#d1d5db]{r.name}[/]   "
                    f"[#22c55e]↑ {r.ahead}[/]   [#ef4444]↓ {r.behind}[/]"
                )
            self.query_one("#status-remotes", Static).update("\n".join(lines))
        else:
            self.query_one("#status-remotes", Static).update("[#6b7280]No remotes configured[/]")

    def _apply_commits(self, repo_path: Path, data: dict) -> None:
        table: DataTable = self.query_one("#commits-table", DataTable)
        table.clear()
        commits = data["commits"]
        graph_text = data["graph"]
        graph_static: Static = self.query_one("#commits-graph", Static)
        if graph_text and not graph_text.startswith("Error"):
            # Colorize graph characters using sentinels so successive
            # replacements can't feed into each other (a literal '/' from
            # an earlier '[/]' insertion must not be re-substituted).
            colored_lines: list[str] = []
            STAR, PIPE, SLASH, BACK = "\x01", "\x02", "\x03", "\x04"
            for line in graph_text.splitlines():
                tagged = (
                    line.replace("*", STAR)
                        .replace("|", PIPE)
                        .replace("/", SLASH)
                        .replace("\\", BACK)
                )
                tagged = re.sub(
                    r"\b([0-9a-f]{7})\b",
                    r"[bold #8b5cf6]\1[/]",
                    tagged,
                )
                tagged = (
                    tagged.replace(STAR, "[#8b5cf6]*[/]")
                          .replace(PIPE, "[#1f2937]|[/]")
                          .replace(SLASH, "[#1f2937]/[/]")
                          .replace(BACK, "[#1f2937]\\\\[/]")
                )
                colored_lines.append(tagged)
            graph_static.update("\n".join(colored_lines))
        else:
            graph_static.update(f"[dim italic]{graph_text or 'No commits'}[/]")

        if not commits:
            table.add_row("—", "No commits", "", "", "", "")
            return

        # ── Stats summary bar ─────────────────────────────────────────
        total_ins = sum(c.insertions for c in commits)
        total_del = sum(c.deletions for c in commits)
        total_files = sum(c.files_changed for c in commits)
        authors = len(set(c.author for c in commits))
        hints: Static = self.query_one("#commits-hints", Static)
        hints.update(
            f"[dim #6b7280]  {len(commits)} commits · "
            f"[#22c55e]+{total_ins}[/] / [#ef4444]-{total_del}[/] lines · "
            f"{total_files} files · {authors} author{'s' if authors != 1 else ''} · "
            f"Enter or d = view diff[/]"
        )

        for c in commits:
            pm = Text()
            pm.append(f"+{c.insertions}", style="bold #22c55e")
            pm.append(" ")
            pm.append(f"-{c.deletions}", style="bold #ef4444")
            table.add_row(
                c.short_hash, c.author, c.date,
                c.message[:60], str(c.files_changed), pm,
            )

    def _apply_diff(self, repo_path: Path, data: dict) -> None:
        file_list: ListView = self.query_one("#diff-file-list", ListView)
        content: Static = self.query_one("#diff-content", Static)
        file_list.clear()
        content.update("[dim italic]← Select a file to view its diff[/]")

        changed = data["changed"]
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

    def _apply_branches(self, repo_path: Path, data: dict) -> None:
        branch_list: ListView = self.query_one("#branch-list", ListView)
        branch_list.clear()
        branches = data["branches"]
        header = self.query_one("#branch-header", Static)
        if not branches:
            header.update("[#6b7280]Local branches[/]")
            branch_list.append(ListItem(Static(
                "\n   [dim #6b7280]No local branches found.[/]\n"
                "   [dim #6b7280]Press [#8b5cf6]n[/] to create one.[/]",
                markup=True,
            )))
            return
        tracked = sum(1 for b in branches if b.has_upstream)
        header.update(
            f"[bold #d1d5db]Local branches[/]  "
            f"[#6b7280]{len(branches)} total · {tracked} tracked[/]"
        )
        for b in branches:
            branch_list.append(BranchListItem(b))

    def _apply_remotes(self, repo_path: Path, data: dict) -> None:
        remotes = data["remotes"]
        lines: list[str] = []
        if not remotes:
            lines.append("[dim italic]No remotes configured[/]")
        else:
            for r in remotes:
                lines.append(f"[bold #8b5cf6]{r.name}[/]")
                lines.append(f"  [bold]URL:[/]   [dim]{r.url}[/]")
                if r.ahead or r.behind:
                    parts = []
                    if r.ahead:
                        parts.append(f"[bold #22c55e]↑ {r.ahead} ahead[/]")
                    if r.behind:
                        parts.append(f"[bold #ef4444]↓ {r.behind} behind[/]")
                    lines.append(f"  [bold]Sync:[/]  {' · '.join(parts)}")
                else:
                    lines.append("  [bold]Sync:[/]  [#22c55e]✓ Up to date[/]")
                lines.append("")
        self.query_one("#remotes-content", Static).update("\n".join(lines))

    def _apply_tags(self, repo_path: Path, data: dict) -> None:
        table: DataTable = self.query_one("#tags-table", DataTable)
        table.clear()
        tags = data["tags"]
        header = self.query_one("#tags-header", Static)
        if not tags:
            header.update("[#6b7280]Tags[/]")
            table.add_row("—", "This repo has no tags yet", "", "")
            return
        header.update(
            f"[bold #d1d5db]Tags[/]  [#6b7280]{len(tags)} shown[/]"
        )
        for t in tags:
            table.add_row(t.name, t.date, t.tagger, t.message[:60])

    def _apply_tree(self, repo_path: Path, data: dict) -> None:
        tree_widget: Tree = self.query_one("#tree-widget", Tree)
        tree_widget.clear()
        tree_widget.root.label = Text.from_markup(
            f"[bold #8b5cf6]{repo_path.name}[/]"
        )
        tree_widget.root.expand()

        file_paths = data["files"]
        if not file_paths:
            tree_widget.root.add_leaf("[dim italic]No tracked files found[/]")
            return

        # Build a nested dict then populate the Textual Tree
        root_dict: dict = {}

        def _insert(d: dict, parts: list[str]) -> None:
            if not parts:
                return
            head, *tail = parts
            if tail:
                d.setdefault(head, {})
                if isinstance(d[head], dict):
                    _insert(d[head], tail)
            else:
                d[head] = None  # leaf = file

        for fp in file_paths:
            _insert(root_dict, fp.replace("\\", "/").split("/"))

        # Store the full path for each leaf so we can open it on Enter
        def _build(node, d: dict, prefix: str = "") -> None:
            dirs = sorted(k for k, v in d.items() if isinstance(v, dict))
            files = sorted(k for k, v in d.items() if v is None)
            for name in dirs:
                child = node.add(
                    f"[bold #8b5cf6]\ud83d\udcc2 {name}[/]",
                    data={"type": "dir"},
                )
                _build(child, d[name], f"{prefix}{name}/")
            for name in files:
                ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
                if ext in ("py", "js", "ts", "go", "rs", "c", "cpp", "java"):
                    label = f"[#22c55e]{name}[/]"
                elif ext in ("md", "rst", "txt"):
                    label = f"[#f59e0b]{name}[/]"
                elif ext in ("json", "yaml", "yml", "toml", "ini", "cfg", "env"):
                    label = f"[#8b5cf6]{name}[/]"
                elif ext in ("sh", "bash", "zsh"):
                    label = f"[#ef4444]{name}[/]"
                else:
                    label = f"[#d1d5db]{name}[/]"
                node.add_leaf(
                    label,
                    data={"type": "file", "path": f"{prefix}{name}"},
                )

        _build(tree_widget.root, root_dict)

    # ── Diff: real-time preview on navigate ──────────────────────────

    def _show_file_diff(self, item: DiffFileItem) -> None:
        if self._current_repo is None:
            return
        content: Static = self.query_one("#diff-content", Static)
        path = self._current_repo
        fp = item.filepath

        if item.file_status == "untracked":
            # Show actual file contents so the user can see what they're about to add.
            try:
                text = get_file_contents(path, fp)
            except Exception as exc:
                content.update(f"[dim italic]Could not read {fp}: {exc}[/]")
                return
            if not text:
                content.update(f"[dim italic](empty new file: {fp})[/]")
                return
            # Best-effort lexer guess from extension; fall back to text.
            ext = fp.rsplit(".", 1)[-1].lower() if "." in fp else ""
            lexer = {
                "py": "python", "js": "javascript", "ts": "typescript",
                "tsx": "tsx", "jsx": "jsx", "go": "go", "rs": "rust",
                "c": "c", "cpp": "cpp", "h": "c", "java": "java",
                "rb": "ruby", "sh": "bash", "bash": "bash", "zsh": "bash",
                "json": "json", "yaml": "yaml", "yml": "yaml",
                "toml": "toml", "md": "markdown", "html": "html", "css": "css",
            }.get(ext, "text")
            content.update(
                Syntax(text, lexer, theme="monokai",
                       line_numbers=True, word_wrap=False, indent_guides=True)
            )
            return

        staged = item.file_status == "staged"
        diff_text = get_file_diff(path, fp, staged=staged)
        if not diff_text or not diff_text.strip():
            label = "staged" if staged else "unstaged"
            content.update(f"[dim italic](no {label} changes for {fp})[/]")
            return
        # line_numbers=True on diff format renders confusingly because diff
        # line numbers don't match real file line numbers — drop them.
        content.update(
            Syntax(diff_text, "diff", theme="monokai",
                   line_numbers=False, word_wrap=False)
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

    # ── Actions ──────────────────────────────────────────────────────

    def _active_ws_list(self) -> ListView | None:
        """Return the ListView of the active Status workspace sub-tab."""
        try:
            tc: TabbedContent = self.query_one("#workspace-tabs", TabbedContent)
            pane = str(tc.active) if tc.active else ""
        except Exception:
            return None
        mapping = {
            "ws-staged": "#staged-list",
            "ws-unstaged": "#unstaged-list",
            "ws-untracked": "#untracked-list",
            "ws-stashes": "#stashes-list",
        }
        list_id = mapping.get(pane)
        if not list_id:
            return None
        try:
            return self.query_one(list_id, ListView)
        except Exception:
            return None

    def action_stage_file(self) -> None:
        if self._current_repo is None or self._active_tab() != "status":
            return
        lv = self._active_ws_list()
        if lv is None:
            return
        item = lv.highlighted_child
        if isinstance(item, StatusFileItem) and item.file_status in ("unstaged", "untracked"):
            msg = stage_files(self._current_repo, [item.filepath])
            self.app.notify(msg, timeout=2)
            self._reload_tab("status")
            self._loaded_tabs.discard("diff")

    def action_unstage_file(self) -> None:
        if self._current_repo is None or self._active_tab() != "status":
            return
        lv = self._active_ws_list()
        if lv is None:
            return
        item = lv.highlighted_child
        if isinstance(item, StatusFileItem) and item.file_status == "staged":
            msg = unstage_files(self._current_repo, [item.filepath])
            self.app.notify(msg, timeout=2)
            self._reload_tab("status")
            self._loaded_tabs.discard("diff")

    def action_stage_all(self) -> None:
        if self._current_repo is None:
            return
        path = self._current_repo
        changed = get_changed_files(path)
        total = len(changed.get("unstaged", [])) + len(changed.get("untracked", []))

        def _do() -> None:
            msg = stage_all(path)
            self.app.notify(msg, timeout=2)
            self._reload_tab("status")
            self._loaded_tabs.discard("diff")

        if total > 20:
            async def _after(ok: bool | None) -> None:
                if ok:
                    _do()
            self.app.push_screen(
                ConfirmModal(
                    title="Stage all files?",
                    body=f"[bold]{total}[/] files will be staged. Continue?",
                ),
                _after,
            )
        else:
            _do()

    def action_unstage_all(self) -> None:
        if self._current_repo is None:
            return
        path = self._current_repo
        changed = get_changed_files(path)
        total = len(changed.get("staged", []))

        def _do() -> None:
            msg = unstage_all(path)
            self.app.notify(msg, timeout=2)
            self._reload_tab("status")
            self._loaded_tabs.discard("diff")

        if total > 20:
            async def _after(ok: bool | None) -> None:
                if ok:
                    _do()
            self.app.push_screen(
                ConfirmModal(
                    title="Unstage all files?",
                    body=f"[bold]{total}[/] files will be unstaged. Continue?",
                ),
                _after,
            )
        else:
            _do()

    def action_open_commit(self) -> None:
        if self._current_repo is None:
            return
        path = self._current_repo

        async def _after_commit(message: str | None) -> None:
            if not message:
                # User may have toggled staging inside the modal — refresh anyway.
                for tab in ("status", "diff"):
                    self._loaded_tabs.discard(tab)
                self._load_tab(self._active_tab() or "status")
                return
            result = commit_changes(path, message)
            self.app.notify(result, timeout=4)
            for tab in ("status", "commits", "diff"):
                self._loaded_tabs.discard(tab)
            current_tab = self._active_tab()
            self._load_tab(current_tab or "status")
            self.post_message(self.ReloadRequested())

        self.app.push_screen(CommitModal(repo_path=path), _after_commit)

    def action_new_branch(self) -> None:
        if self._current_repo is None:
            return

        async def _after_create(name: str | None) -> None:
            if not name:
                return
            result = create_branch(self._current_repo, name)
            self.app.notify(result, timeout=3)
            self._reload_tab("branches")
            self._loaded_tabs.discard("status")
            self.post_message(self.ReloadRequested())

        try:
            existing = [b.name for b in get_branches(self._current_repo)]
        except Exception:
            existing = []
        self.app.push_screen(NewBranchModal(existing=existing), _after_create)

    def action_stash_create(self) -> None:
        """Open the stash dialog (z key)."""
        if self._current_repo is None:
            return

        async def _after_stash(message: str | None) -> None:
            # message can be "" (no name) or a real string — both are valid
            if message is None:
                return
            result = stash_create(self._current_repo, message)
            self.app.notify(result, timeout=3)
            self._reload_tab("status")
            self.post_message(self.ReloadRequested())

        self.app.push_screen(StashModal(), _after_stash)

    def action_stash_pop(self) -> None:
        """Pop the top stash (Z key) — warn first if working tree is dirty."""
        if self._current_repo is None:
            return
        path = self._current_repo

        def _do() -> None:
            result = stash_pop(path)
            self.app.notify(result, timeout=3)
            self._reload_tab("status")
            self.post_message(self.ReloadRequested())

        dirty, summary = is_dirty(path)
        if dirty:
            async def _after(ok: bool | None) -> None:
                if ok:
                    _do()
            self.app.push_screen(
                ConfirmModal(
                    title="Pop stash over dirty tree?",
                    body=(
                        f"Working tree has [bold]{summary}[/]. "
                        "Pop may produce merge conflicts. Continue?"
                    ),
                    danger=True,
                ),
                _after,
            )
        else:
            _do()

    def action_fetch(self) -> None:
        """Fetch from all remotes (f key in Remotes tab) — runs in background."""
        if self._current_repo is None:
            return
        self.app.notify("Fetching…", timeout=2)
        path = self._current_repo
        self.run_worker(
            lambda: ("fetch", git_fetch(path)),
            thread=True, group="git_op", exclusive=False,
        )

    def action_pull(self) -> None:
        """Pull from the tracking branch (p key) — confirm if tree is dirty."""
        if self._current_repo is None:
            return
        path = self._current_repo

        def _do() -> None:
            self.app.notify("Pulling…", timeout=2)
            self.run_worker(
                lambda: ("pull", git_pull(path)),
                thread=True, group="git_op", exclusive=False,
            )

        dirty, summary = is_dirty(path)
        if dirty:
            async def _after(ok: bool | None) -> None:
                if ok:
                    _do()
            self.app.push_screen(
                ConfirmModal(
                    title="Pull over dirty tree?",
                    body=(
                        f"Working tree has [bold]{summary}[/]. "
                        "Pull may fail or create conflicts. Continue?"
                    ),
                    danger=True,
                ),
                _after,
            )
        else:
            _do()

    def action_push(self) -> None:
        """Push to the tracking branch (P key) — always confirm."""
        if self._current_repo is None:
            return
        path = self._current_repo
        repo_name = path.name

        def _do() -> None:
            self.app.notify("Pushing…", timeout=2)
            self.run_worker(
                lambda: ("push", git_push(path)),
                thread=True, group="git_op", exclusive=False,
            )

        async def _after(ok: bool | None) -> None:
            if ok:
                _do()

        self.app.push_screen(
            ConfirmModal(
                title=f"Push {repo_name}?",
                body=(
                    f"Push current branch from [bold #8b5cf6]{repo_name}[/] to its "
                    "tracking remote?"
                ),
            ),
            _after,
        )

    def on_worker_state_changed(self, event) -> None:
        """Handle results from background workers (tab-load + git_op)."""
        from textual.worker import WorkerState
        group = getattr(event.worker, "group", None) or ""

        # Tab loaders
        if group.startswith("tabload:"):
            event.stop()
            if event.state == WorkerState.SUCCESS and event.worker.result is not None:
                status, tab_id, token, path, data = event.worker.result
                self._on_tab_result(tab_id, token, path, status, data)
            elif event.state == WorkerState.ERROR:
                tab_id = group.split(":", 1)[1]
                hint, detail = classify_error(event.worker.error)
                self.app.notify(f"{tab_id}: {hint}", severity="error", timeout=5)
                _record_app_error(self.app, detail)
                self._loaded_tabs.discard(tab_id)
            return

        if group != "git_op":
            return
        event.stop()  # Don't let it bubble to the App's handler
        if event.state == WorkerState.SUCCESS and event.worker.result is not None:
            op, result_msg = event.worker.result
            self.app.notify(result_msg, timeout=5)
            if op in ("pull", "fetch"):
                for tab in ("status", "commits", "remotes"):
                    self._loaded_tabs.discard(tab)
            else:
                self._loaded_tabs.discard("remotes")
            self._load_tab(self._active_tab())
            self.post_message(self.ReloadRequested())
        elif event.state == WorkerState.ERROR:
            hint, detail = classify_error(event.worker.error)
            self.app.notify(hint, severity="error", timeout=6)
            _record_app_error(self.app, detail)


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
        branch_name = item.branch_info.name
        path = self._current_repo
        phrase = f"delete {branch_name}"

        async def _after(ok: bool | None) -> None:
            if not ok:
                return
            result = delete_branch(path, branch_name)
            if result.startswith("Error"):
                hint, detail = classify_error(result)
                self.app.notify(hint, severity="error", timeout=6)
                _record_app_error(self.app, detail)
            else:
                self.app.notify(result, timeout=3)
            self._reload_tab("branches")
            self.post_message(self.ReloadRequested())

        self.app.push_screen(
            TypedConfirmModal(
                title=f"Delete branch '{branch_name}'?",
                body=(
                    f"This will permanently delete branch "
                    f"[bold #ef4444]{branch_name}[/] from this repo."
                ),
                phrase=phrase,
            ),
            _after,
        )

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

    def on_tree_node_selected(self, event: Tree.NodeSelected) -> None:
        """Enter on a tree leaf → open file preview modal."""
        if event.node.tree.id != "tree-widget":
            return
        data = event.node.data
        if data and data.get("type") == "file" and self._current_repo is not None:
            filepath: str = data["path"]
            content = get_file_contents(self._current_repo, filepath)
            self.app.push_screen(FilePreviewModal(filepath, content))

    def on_key(self, event) -> None:
        """Route key presses depending on the active tab."""
        tab = self._active_tab()
        if event.key == "d":
            if tab == "branches":
                self._delete_selected_branch()
                event.stop()
            elif tab == "commits":
                self._open_commit_diff()
                event.stop()
        elif event.key == "f" and tab == "remotes":
            self.action_fetch()
            event.stop()
        elif event.key == "p" and tab == "remotes":
            self.action_pull()
            event.stop()
        elif event.key == "P" and tab == "remotes":
            self.action_push()
            event.stop()
