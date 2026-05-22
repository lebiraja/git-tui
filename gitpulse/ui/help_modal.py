"""
help_modal.py — Keyboard shortcut cheat-sheet modal for GitPulse.

Opened with '?'. Lists the global and context keybindings in a single
centered panel.
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import ModalScreen
from textual.widgets import Static
from textual.containers import Container

_SECTIONS: list[tuple[str, list[tuple[str, str]]]] = [
    ("Global", [
        ("/", "Search / filter repos"),
        ("r", "Refresh — rescan all repos"),
        ("w", "Toggle watch mode"),
        ("d", "Activity digest"),
        (":", "Bulk action palette"),
        ("b", "Stale-branch cleanup"),
        ("[ ]", "Previous / next tab"),
        ("?", "This help"),
        ("q", "Quit"),
    ]),
    ("Status tab", [
        ("s / u", "Stage / unstage file"),
        ("a / U", "Stage all / unstage all"),
        ("c", "Commit staged changes"),
        ("n", "New branch"),
        ("z / Z", "Create / pop stash"),
    ]),
    ("Other tabs", [
        ("Enter", "Switch branch · view commit diff · preview file"),
        ("d", "Delete branch · view commit diff"),
        ("f / p / P", "Fetch / pull / push (Remotes)"),
    ]),
    ("Sidebar", [
        ("↑ ↓", "Navigate repositories"),
        ("Space", "Toggle multi-select"),
        ("*", "Select all visible"),
    ]),
]


class HelpModal(ModalScreen):
    """Centered keyboard-shortcut reference."""

    BINDINGS = [Binding("escape,q,question_mark", "close", "Close", show=True)]

    DEFAULT_CSS = """
    HelpModal {
        align: center middle;
    }
    #help-frame {
        width: 64;
        height: auto;
        max-height: 90%;
        padding: 1 2;
        background: #111827;
        border: solid #8b5cf6;
    }
    #help-title {
        text-style: bold;
        color: #8b5cf6;
        width: 100%;
        text-align: center;
        margin-bottom: 1;
    }
    #help-body {
        width: 100%;
        height: auto;
    }
    #help-footer {
        width: 100%;
        text-align: center;
        color: #6b7280;
        margin-top: 1;
    }
    """

    def compose(self) -> ComposeResult:
        with Container(id="help-frame"):
            yield Static("Keyboard Shortcuts", id="help-title", markup=False)
            yield Static(self._body(), id="help-body", markup=True)
            yield Static("Esc / q to close", id="help-footer", markup=False)

    @staticmethod
    def _body() -> str:
        lines: list[str] = []
        for section, rows in _SECTIONS:
            lines.append(f"[bold #d1d5db]{section}[/]")
            for key, desc in rows:
                lines.append(f"  [#8b5cf6]{key:<10}[/] [#d1d5db]{desc}[/]")
            lines.append("")
        return "\n".join(lines).rstrip()

    def action_close(self) -> None:
        self.dismiss()
