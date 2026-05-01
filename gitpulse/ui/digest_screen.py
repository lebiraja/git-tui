"""
digest_screen.py — Activity digest TUI modal for GitPulse.

Full-screen modal accessed via 'D' in the main app. Shows commits by the
current user(s) across all scanned repos in a configurable time window.
"""

from __future__ import annotations

from datetime import datetime, timezone

from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import ModalScreen
from textual.widgets import Static, Button
from textual.containers import Container, ScrollableContainer, Horizontal

try:
    from gitpulse.digest import Digest, build_digest, render_markdown
    from gitpulse.git_ops import RepoInfo
    from gitpulse.utils import parse_since, relative_time
except ImportError:
    from digest import Digest, build_digest, render_markdown  # type: ignore
    from git_ops import RepoInfo  # type: ignore
    from utils import parse_since, relative_time  # type: ignore


_WINDOWS = {
    "1": ("1d", "Today"),
    "7": ("7d", "7 days"),
    "3": ("30d", "30 days"),
}


class DigestScreen(ModalScreen):
    """Full-screen activity digest modal."""

    BINDINGS = [
        Binding("escape,q", "close", "Close", show=True),
        Binding("1", "window_1d", "Today", show=True),
        Binding("7", "window_7d", "7d", show=True),
        Binding("3", "window_30d", "30d", show=True),
        Binding("m", "copy_markdown", "Copy MD", show=True),
    ]

    DEFAULT_CSS = """
    DigestScreen {
        align: center middle;
    }
    #digest-frame {
        width: 95%;
        height: 90%;
        background: #1e2030;
        border: thick #7aa2f7;
    }
    #digest-header {
        dock: top;
        height: 3;
        background: #24283b;
        color: #7aa2f7;
        text-style: bold;
        padding: 0 2;
        border-bottom: heavy #3b4261;
        layout: horizontal;
        align: left middle;
    }
    #digest-window-label {
        width: auto;
        color: #bb9af7;
        margin-left: 2;
    }
    #digest-scroll {
        width: 100%;
        height: 1fr;
        padding: 0 1;
    }
    #digest-body {
        padding: 1 1;
    }
    #digest-footer {
        dock: bottom;
        height: 1;
        background: #1e2030;
        color: #565f89;
        padding: 0 1;
        border-top: solid #3b4261;
    }
    """

    def __init__(
        self,
        repos: list[RepoInfo],
        author_patterns: list[str] | None = None,
        default_window: str = "1d",
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self._repos = repos
        self._author_patterns = author_patterns or []
        self._window = default_window
        self._digest: Digest | None = None

    def compose(self) -> ComposeResult:
        with Container(id="digest-frame"):
            with Horizontal(id="digest-header"):
                yield Static("📋 Activity Digest", markup=False)
                yield Static("", id="digest-window-label")
            with ScrollableContainer(id="digest-scroll"):
                yield Static(
                    "[dim italic]Loading digest…[/]",
                    id="digest-body",
                    markup=True,
                )
            yield Static(
                "  1=today  7=7d  3=30d  m=copy markdown  Esc/q=close",
                id="digest-footer",
                markup=False,
            )

    def on_mount(self) -> None:
        self._load_digest()

    def _load_digest(self) -> None:
        label: Static = self.query_one("#digest-window-label", Static)
        label.update(f"[#bb9af7]window: {self._window}[/]")

        body: Static = self.query_one("#digest-body", Static)
        body.update("[dim italic]Computing digest…[/]")

        try:
            since_ts = parse_since(self._window)
        except ValueError as e:
            body.update(f"[bold #f7768e]Error: {e}[/]")
            return

        # Run in a worker so we don't block the UI
        self.run_worker(
            lambda: build_digest(self._repos, since_ts, self._author_patterns),
            thread=True,
            group="digest",
        )

    def on_worker_state_changed(self, event) -> None:
        from textual.worker import WorkerState
        if event.state == WorkerState.SUCCESS and event.worker.result is not None:
            self._digest = event.worker.result
            self._render_digest()
        elif event.state == WorkerState.ERROR:
            body: Static = self.query_one("#digest-body", Static)
            body.update(f"[bold #f7768e]Error building digest: {event.worker.error}[/]")

    def _render_digest(self) -> None:
        d = self._digest
        if d is None:
            return

        body: Static = self.query_one("#digest-body", Static)

        if d.total_commits == 0:
            body.update(
                "[dim italic]  No commits found for this window and author pattern.[/]\n"
                "[dim #565f89]  Tip: configure author emails in ~/.config/gitpulse/config.toml[/]"
            )
            return

        lines: list[str] = []
        since_str = datetime.fromtimestamp(d.since_ts, tz=timezone.utc).strftime("%Y-%m-%d %H:%M")
        lines.append(
            f"[bold #7aa2f7]{d.total_commits}[/] commits across "
            f"[bold #9ece6a]{d.repos_active}[/] repos  "
            f"[#9ece6a]+{d.total_insertions}[/] [#f7768e]-{d.total_deletions}[/] lines  "
            f"[dim]since {since_str} UTC[/]"
        )
        lines.append("[dim #3b4261]─" * 60 + "[/]")

        for rd in d.by_repo:
            lines.append(
                f"\n[bold #bb9af7]📁 {rd.repo.name}[/]  "
                f"[dim]{len(rd.commits)} commit{'s' if len(rd.commits) != 1 else ''}  "
                f"[#9ece6a]+{rd.insertions}[/]"
                f" [#f7768e]-{rd.deletions}[/][/dim]"
            )
            for c in rd.commits:
                rel = relative_time(c.ts)
                stats = f"[#9ece6a]+{c.insertions}[/] [#f7768e]-{c.deletions}[/]" if (c.insertions or c.deletions) else ""
                msg = c.message[:70]
                lines.append(
                    f"  [dim #7aa2f7]{c.short_hash}[/]  {msg}"
                    f"  {stats}  [dim #565f89]{rel}[/]"
                )

        body.update("\n".join(lines))

    def action_window_1d(self) -> None:
        self._window = "1d"
        self._load_digest()

    def action_window_7d(self) -> None:
        self._window = "7d"
        self._load_digest()

    def action_window_30d(self) -> None:
        self._window = "30d"
        self._load_digest()

    def action_copy_markdown(self) -> None:
        if self._digest is None:
            self.app.notify("No digest to copy yet", timeout=2)
            return
        md = render_markdown(self._digest)
        try:
            import pyperclip
            pyperclip.copy(md)
            self.app.notify("Markdown copied to clipboard ✓", timeout=3)
        except Exception:
            self.app.notify("pyperclip not available — printed to stderr", timeout=3)
            import sys
            print(md, file=sys.stderr)

    def action_close(self) -> None:
        self.dismiss()
