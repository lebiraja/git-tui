"""
header.py — Slim application header for GitPulse.

A single-row bar holding the logo, the seven content tabs, and the global
action hints. Replaces Textual's built-in Header. Clicking a tab (or the
prev/next tab keybindings handled by the app) posts an AppHeader.TabChanged
message; the app switches the ContentSwitcher pane in response.
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.message import Message
from textual.widget import Widget
from textual.widgets import Static
from textual.containers import Horizontal

# (tab id, display label) — order defines left-to-right tab order.
TABS: list[tuple[str, str]] = [
    ("status", "Status"),
    ("commits", "Commits"),
    ("diff", "Diff"),
    ("branches", "Branches"),
    ("remotes", "Remotes"),
    ("tags", "Tags"),
    ("tree", "Tree"),
]

TAB_IDS = [t[0] for t in TABS]


class HeaderTab(Static):
    """A single clickable tab label in the header."""

    def __init__(self, tab_id: str, label: str, active: bool = False, **kwargs) -> None:
        super().__init__(label, **kwargs)
        self.tab_id = tab_id
        if active:
            self.add_class("-active")

    def on_click(self) -> None:
        self.post_message(AppHeader.TabChanged(self.tab_id))


class AppHeader(Widget):
    """Slim top header: logo · tabs · action hints."""

    class TabChanged(Message):
        """Posted when the active content tab should change."""

        def __init__(self, tab_id: str) -> None:
            super().__init__()
            self.tab_id = tab_id

    def __init__(self, active_tab: str = "status", **kwargs) -> None:
        super().__init__(**kwargs)
        self._active = active_tab

    def compose(self) -> ComposeResult:
        yield Static(
            "[bold #d1d5db]GitPulse[/]  [#6b7280]Fleet overview[/]",
            id="header-logo",
            markup=True,
        )
        with Horizontal(id="header-tabs"):
            for tid, label in TABS:
                yield HeaderTab(
                    tid, label, active=(tid == self._active), id=f"htab-{tid}"
                )
        yield Static(
            "[#6b7280]/ Search   r Refresh   ? Help[/]",
            id="header-actions",
            markup=True,
        )

    def set_active(self, tab_id: str) -> None:
        """Highlight *tab_id* and clear the highlight from the others."""
        self._active = tab_id
        for tid in TAB_IDS:
            try:
                tab = self.query_one(f"#htab-{tid}", HeaderTab)
            except Exception:
                continue
            tab.set_class(tid == tab_id, "-active")
