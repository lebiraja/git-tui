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
    """Centered keyboard-shortcut reference with a live recent-errors panel."""

    BINDINGS = [Binding("escape,q,question_mark", "close", "Close", show=True)]

    DEFAULT_CSS = """
    HelpModal {
        align: center middle;
    }
    #help-frame {
        width: 70;
        height: auto;
        max-height: 90%;
        padding: 1 2;
        background: #111827;
        border: solid #8b5cf6;
        border-title-align: left;
    }
    #help-title {
        text-style: bold;
        color: #8b5cf6;
        width: 100%;
        text-align: center;
        margin-bottom: 1;
    }
    #help-body, #help-errors {
        width: 100%;
        height: auto;
    }
    #help-errors {
        margin-top: 1;
        border-top: solid #1f2937;
        padding-top: 1;
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
            yield Static(self._errors_panel(), id="help-errors", markup=True)
            yield Static("Esc / q to close", id="help-footer", markup=False)

    def _body(self) -> str:
        lines: list[str] = []
        documented: set[str] = set()
        for section, rows in _SECTIONS:
            lines.append(f"[bold #d1d5db]{section}[/]")
            for key, desc in rows:
                lines.append(f"  [#8b5cf6]{key:<10}[/] [#d1d5db]{desc}[/]")
                for k in key.replace("/", " ").split():
                    documented.add(k.strip().lower())
            lines.append("")

        # Auto-discover any bindings on the app or focused widget not yet listed.
        extras: list[tuple[str, str]] = []
        seen: set[str] = set()
        try:
            app_bindings = getattr(self.app, "BINDINGS", []) or []
            main_panel = self.app.query("MainPanel")
            panel_bindings = list(main_panel.first().BINDINGS) if main_panel else []
            for b in list(app_bindings) + list(panel_bindings):
                key = getattr(b, "key", None) or (b[0] if isinstance(b, tuple) else None)
                desc = getattr(b, "description", "") or (b[2] if isinstance(b, tuple) and len(b) > 2 else "")
                if not key or key.lower() in documented or key.lower() in seen:
                    continue
                if not desc:
                    continue
                seen.add(key.lower())
                extras.append((key, desc))
        except Exception:
            pass
        if extras:
            lines.append("[bold #d1d5db]Other bindings[/]")
            for key, desc in extras:
                lines.append(f"  [#8b5cf6]{key:<10}[/] [#d1d5db]{desc}[/]")
            lines.append("")
        return "\n".join(lines).rstrip()

    def _errors_panel(self) -> str:
        log = getattr(self.app, "_error_log", None) or []
        if not log:
            return "[bold #d1d5db]Recent errors[/]\n  [dim #6b7280]none[/]"
        lines = ["[bold #d1d5db]Recent errors[/] [dim #6b7280](last "
                 f"{min(len(log), 5)})[/]"]
        for detail in log[-5:]:
            first = (detail or "").splitlines()[0][:80]
            lines.append(f"  [#ef4444]•[/] [#d1d5db]{first}[/]")
        return "\n".join(lines)

    def action_close(self) -> None:
        self.dismiss()
