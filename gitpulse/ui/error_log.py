"""
error_log.py — Modal screen showing recorded error details.

The app records raw error text into a capped ring buffer as operations fail.
This screen is how the user actually reads it: without a view, a failure that
affects one repo out of forty leaves no trace beyond a two-second toast.
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Static


class ErrorLogScreen(ModalScreen[None]):
    """Scrollable list of recorded errors, newest first."""

    DEFAULT_CSS = """
    ErrorLogScreen {
        align: center middle;
    }
    #errorlog-box {
        width: 96;
        max-width: 90%;
        height: auto;
        max-height: 90%;
        padding: 1 2;
        background: #111827;
        border: round #ef4444;
    }
    #errorlog-title {
        width: 100%;
        color: #d1d5db;
        margin-bottom: 1;
    }
    #errorlog-body {
        width: 100%;
        height: auto;
        max-height: 28;
    }
    .errorlog-row {
        width: 100%;
        height: auto;
        color: #d1d5db;
        margin-bottom: 1;
    }
    #errorlog-empty {
        width: 100%;
        height: auto;
    }
    #errorlog-hint {
        width: 100%;
        margin-top: 1;
        border-top: solid #1f2937;
        padding-top: 1;
    }
    """

    BINDINGS = [
        Binding("escape", "dismiss_log", "Close", id="errorlog.close", show=True),
        Binding("q", "dismiss_log", "Close", id="errorlog.quit", show=False),
    ]

    def __init__(self, errors: list[str], **kwargs) -> None:
        super().__init__(**kwargs)
        self._errors = list(reversed(errors))  # newest first

    def compose(self) -> ComposeResult:
        count = len(self._errors)
        label = "entry" if count == 1 else "entries"

        with Vertical(id="errorlog-box"):
            yield Static(f"[bold]Error log[/]  ·  {count} {label}", id="errorlog-title")
            with VerticalScroll(id="errorlog-body"):
                if not self._errors:
                    yield Static(
                        "[#6b7280]No errors recorded this session.[/]",
                        id="errorlog-empty",
                    )
                for i, detail in enumerate(self._errors):
                    # Error text is arbitrary (git stderr) and may contain
                    # square brackets, so render it without markup parsing.
                    yield Static(
                        f"{i + 1:>3}  {detail}",
                        classes="errorlog-row",
                        markup=False,
                    )
            yield Static("[#6b7280]esc close[/]", id="errorlog-hint")

    def action_dismiss_log(self) -> None:
        self.dismiss(None)
