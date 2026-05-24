"""
confirm_modal.py — Shared confirmation modals for GitPulse.

ConfirmModal       — yes/no with Enter/Esc; returns bool via dismiss().
TypedConfirmModal  — user must type a phrase before confirm is enabled.
DirtyTreeModal     — three-way prompt (Stash & switch / Switch anyway / Cancel)
                     used before branch switching when the tree is dirty.
                     Resolves to one of: "stash", "force", None.
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Static


_BASE_CSS = """
ConfirmModal, TypedConfirmModal, DirtyTreeModal {
    align: center middle;
}
.cm-frame {
    width: 64;
    max-width: 90%;
    height: auto;
    padding: 1 2;
    background: #111827;
    border: round #8b5cf6;
}
.cm-frame.-danger { border: round #ef4444; }
.cm-title {
    text-style: bold;
    width: 100%;
    height: 1;
    margin-bottom: 1;
    content-align: left middle;
}
.cm-title.-danger { color: #ef4444; }
.cm-title.-safe   { color: #8b5cf6; }
.cm-body {
    color: #d1d5db;
    width: 100%;
    height: auto;
    margin-bottom: 1;
}
.cm-hint {
    color: #f59e0b;
    width: 100%;
    height: 1;
    margin-bottom: 1;
}
.cm-input {
    width: 100%;
    margin-bottom: 1;
}
.cm-btns {
    width: 100%;
    height: 3;
    align: right middle;
    padding-top: 1;
}
.cm-btns Button {
    margin: 0 0 0 1;
    min-width: 12;
}
"""


class ConfirmModal(ModalScreen):
    """Simple yes/no confirmation. dismiss(True) on confirm, dismiss(False) on cancel."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel", show=True),
        Binding("enter", "confirm", "Confirm", show=True),
    ]

    DEFAULT_CSS = _BASE_CSS

    def __init__(
        self,
        title: str,
        body: str,
        *,
        danger: bool = False,
        confirm_label: str = "Confirm",
        cancel_label: str = "Cancel",
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self._title = title
        self._body = body
        self._danger = danger
        self._confirm_label = confirm_label
        self._cancel_label = cancel_label

    def compose(self) -> ComposeResult:
        frame_classes = "cm-frame -danger" if self._danger else "cm-frame"
        title_classes = "cm-title -danger" if self._danger else "cm-title -safe"
        with Container(classes=frame_classes):
            yield Static(self._title, classes=title_classes, markup=False)
            yield Static(self._body, classes="cm-body", markup=True)
            with Horizontal(classes="cm-btns"):
                yield Button(
                    self._confirm_label,
                    id="cm-confirm",
                    variant="error" if self._danger else "primary",
                )
                yield Button(self._cancel_label, id="cm-cancel")

    def on_mount(self) -> None:
        self.query_one("#cm-confirm", Button).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "cm-confirm":
            self.dismiss(True)
        else:
            self.dismiss(False)

    def action_confirm(self) -> None:
        self.dismiss(True)

    def action_cancel(self) -> None:
        self.dismiss(False)


class TypedConfirmModal(ModalScreen):
    """User must type `phrase` exactly. dismiss(True) on match, dismiss(False) on cancel."""

    BINDINGS = [Binding("escape", "cancel", "Cancel", show=True)]

    DEFAULT_CSS = _BASE_CSS

    def __init__(self, title: str, body: str, phrase: str, **kwargs) -> None:
        super().__init__(**kwargs)
        self._title = title
        self._body = body
        self._phrase = phrase

    def compose(self) -> ComposeResult:
        with Container(classes="cm-frame -danger"):
            yield Static(self._title, classes="cm-title -danger", markup=False)
            yield Static(self._body, classes="cm-body", markup=True)
            yield Static(f"Type exactly: {self._phrase}", classes="cm-hint", markup=False, id="cm-typed-hint")
            yield Input(placeholder=self._phrase, classes="cm-input", id="cm-typed-input")
            with Horizontal(classes="cm-btns"):
                yield Button("Confirm", id="cm-confirm", variant="error")
                yield Button("Cancel", id="cm-cancel")

    def on_mount(self) -> None:
        self.query_one("#cm-typed-input", Input).focus()

    def on_input_submitted(self, _event: Input.Submitted) -> None:
        self._try_confirm()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "cm-confirm":
            self._try_confirm()
        else:
            self.dismiss(False)

    def _try_confirm(self) -> None:
        val = self.query_one("#cm-typed-input", Input).value.strip()
        if val == self._phrase:
            self.dismiss(True)
        else:
            self.query_one("#cm-typed-hint", Static).update(
                f"Must match exactly: {self._phrase}", markup=False
            )

    def action_cancel(self) -> None:
        self.dismiss(False)


class DirtyTreeModal(ModalScreen):
    """Three-way prompt before switching branch with a dirty tree.

    Dismisses with one of: "stash", "force", None (cancel).
    """

    BINDINGS = [
        Binding("escape", "cancel", "Cancel", show=True),
        Binding("s", "stash", "Stash & switch", show=True),
        Binding("f", "force", "Switch anyway", show=True),
    ]

    DEFAULT_CSS = _BASE_CSS

    def __init__(self, repo_name: str, dirty_summary: str, target_branch: str, **kwargs) -> None:
        super().__init__(**kwargs)
        self._repo_name = repo_name
        self._summary = dirty_summary
        self._target = target_branch

    def compose(self) -> ComposeResult:
        with Container(classes="cm-frame -danger"):
            yield Static(
                f"Uncommitted changes in {self._repo_name}",
                classes="cm-title -danger",
                markup=False,
            )
            yield Static(
                f"Working tree is dirty: [bold]{self._summary}[/].\n"
                f"Switching to [bold #8b5cf6]{self._target}[/] may lose unstaged work.",
                classes="cm-body",
                markup=True,
            )
            with Horizontal(classes="cm-btns"):
                yield Button("Stash & switch", id="cm-stash", variant="primary")
                yield Button("Switch anyway", id="cm-force", variant="error")
                yield Button("Cancel", id="cm-cancel")

    def on_mount(self) -> None:
        self.query_one("#cm-stash", Button).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id
        if bid == "cm-stash":
            self.dismiss("stash")
        elif bid == "cm-force":
            self.dismiss("force")
        else:
            self.dismiss(None)

    def action_stash(self) -> None:
        self.dismiss("stash")

    def action_force(self) -> None:
        self.dismiss("force")

    def action_cancel(self) -> None:
        self.dismiss(None)
