"""
summary_cards.py — Horizontal summary cards for the GitPulse Status pane.

Five equal-width thin-bordered cards summarising the selected repository:
Branch · Commits · Status · Stashes · Ahead/Behind. Populated straight from
the existing RepoInfo fields plus the stash list — no new git queries.
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.widgets import Static

try:
    from gitpulse.git_ops import RepoInfo, RepoStatus, StashEntry
except ImportError:
    from git_ops import RepoInfo, RepoStatus, StashEntry  # type: ignore[no-redef]

_TEXT = "#d1d5db"
_MUTED = "#6b7280"
_ACCENT = "#8b5cf6"
_GREEN = "#22c55e"
_YELLOW = "#f59e0b"
_RED = "#ef4444"


class SummaryCard(Static):
    """A single bordered summary card with a border-title label."""

    def __init__(self, card_title: str, **kwargs) -> None:
        super().__init__("", markup=True, **kwargs)
        self._card_title = card_title

    def on_mount(self) -> None:
        self.border_title = self._card_title


class SummaryCards(Static):
    """Row of five summary cards describing the selected repository."""

    def compose(self) -> ComposeResult:
        yield SummaryCard("BRANCH", id="card-branch")
        yield SummaryCard("COMMITS", id="card-commits")
        yield SummaryCard("STATUS", id="card-status")
        yield SummaryCard("STASHES", id="card-stashes")
        yield SummaryCard("AHEAD / BEHIND", id="card-ahead")

    def update_cards(
        self,
        info: RepoInfo | None,
        stashes: list[StashEntry] | None = None,
    ) -> None:
        """Populate every card from *info* and the *stashes* list."""
        stashes = stashes or []
        branch = self.query_one("#card-branch", SummaryCard)
        commits = self.query_one("#card-commits", SummaryCard)
        status = self.query_one("#card-status", SummaryCard)
        stash = self.query_one("#card-stashes", SummaryCard)
        ahead = self.query_one("#card-ahead", SummaryCard)

        if info is None:
            for card in (branch, commits, status, stash, ahead):
                card.update("")
            return

        branch.update(f"[{_ACCENT}]{info.branch}[/]")

        n_contrib = info.contributor_count
        contrib = f"{n_contrib} contributor" + ("s" if n_contrib != 1 else "")
        commits.update(f"[bold {_TEXT}]{info.total_commits}[/]\n[{_MUTED}]{contrib}[/]")

        if info.status == RepoStatus.CLEAN:
            s_text, s_color, s_sub = "✓ Clean", _GREEN, "Working tree clean"
        elif info.status == RepoStatus.MODIFIED:
            s_text, s_color = "● Modified", _YELLOW
            s_sub = f"{info.modified_count} changed"
        else:
            s_text, s_color = "● Untracked", _RED
            s_sub = f"{info.modified_count} untracked"
        status.update(f"[{s_color}]{s_text}[/]\n[{_MUTED}]{s_sub}[/]")

        if stashes:
            first = stashes[0].message[:24]
            stash.update(f"[bold {_TEXT}]{len(stashes)}[/]\n[{_MUTED}]{first}[/]")
        else:
            stash.update(f"[bold {_TEXT}]0[/]\n[{_MUTED}]none[/]")

        ahead.update(
            f"[{_GREEN}]↑ {info.ahead}[/]    [{_RED}]↓ {info.behind}[/]"
        )
