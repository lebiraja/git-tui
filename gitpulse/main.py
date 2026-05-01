"""
main.py — GitPulse entry point.

Launches the Textual TUI application. Accepts CLI arguments to configure
the scan root, number of commits to show, and version output.
Repos are sorted by most recent commit date.

Scanning runs in a background worker thread so the UI stays responsive.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.widgets import Header, Footer, Input
from textual.containers import Horizontal, Vertical
from textual.worker import Worker, WorkerState

# Support both installed-package imports (gitpulse.scanner) and
# direct execution (python main.py) by trying package import first.
try:
    from gitpulse.scanner import scan_repos
    from gitpulse.git_ops import get_repo_info, switch_branch, RepoInfo
    from gitpulse.ui.sidebar import RepoSidebar
    from gitpulse.ui.tabs import MainPanel
    from gitpulse.ui.fleet_status import FleetStatus
    from gitpulse.utils import __version__
    from gitpulse import config as _config
except ImportError:
    # Running directly: python main.py
    _THIS_DIR = Path(__file__).resolve().parent
    if str(_THIS_DIR) not in sys.path:
        sys.path.insert(0, str(_THIS_DIR))
    from scanner import scan_repos  # type: ignore[no-redef]
    from git_ops import get_repo_info, switch_branch, RepoInfo  # type: ignore[no-redef]
    from ui.sidebar import RepoSidebar  # type: ignore[no-redef]
    from ui.tabs import MainPanel  # type: ignore[no-redef]
    from ui.fleet_status import FleetStatus  # type: ignore[no-redef]
    from utils import __version__  # type: ignore[no-redef]
    import config as _config  # type: ignore[no-redef]


class GitPulseApp(App):
    """
    GitPulse — A developer-focused Git repository dashboard TUI.

    Scans a root directory for all local git repos and displays live
    status, recent commits, diffs, and branch management.
    Repos are sorted by most recent commit (most active first).
    """

    CSS_PATH = str(Path(__file__).parent / "ui" / "styles.tcss")

    TITLE = "GitPulse"
    SUB_TITLE = "Git Repo Dashboard"

    BINDINGS = [
        Binding("q", "quit", "Quit", show=True),
        Binding("r", "refresh", "Refresh", show=True),
        Binding("slash", "search", "Search", show=True),
        Binding("escape", "clear_search", "Clear", show=False),
        Binding("tab", "focus_next", "Next", show=False),
        Binding("shift+tab", "focus_previous", "Prev", show=False),
    ]

    def __init__(self, root_dir: Path, commits: int = 10, **kwargs) -> None:
        super().__init__(**kwargs)
        self.root_dir = root_dir
        self.commits = commits          # How many commits to show in Commits tab
        self.repos: list[RepoInfo] = []
        self._all_repos: list[RepoInfo] = []  # Unfiltered master list
        self._selected_repo: RepoInfo | None = None
        self._scanning = False          # Guard against concurrent scans

    # -----------------------------------------------------------------
    # Layout
    # -----------------------------------------------------------------

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal(id="app-grid"):
            with Vertical(id="sidebar-column"):
                yield FleetStatus(id="fleet-status")
                yield RepoSidebar(id="sidebar-container")
            yield MainPanel(id="main-panel", commits=self.commits)
        yield Footer()

    # -----------------------------------------------------------------
    # Lifecycle
    # -----------------------------------------------------------------

    def on_mount(self) -> None:
        """Initial scan on startup."""
        self._start_scan()

    # -----------------------------------------------------------------
    # Actions
    # -----------------------------------------------------------------

    def action_refresh(self) -> None:
        """Rescan all repositories (bound to 'r')."""
        if self._scanning:
            self.notify("Scan already in progress…", timeout=2)
            return
        self._start_scan()
        self.notify("Scanning repositories… ⚡", timeout=2)

    def action_search(self) -> None:
        """Focus the search input (bound to '/')."""
        sidebar: RepoSidebar = self.query_one("#sidebar-container", RepoSidebar)
        sidebar.focus_search()

    def action_clear_search(self) -> None:
        """Clear search and refocus repo list."""
        inp = self.query_one("#search-input", Input)
        inp.value = ""
        self.query_one("#repo-list").focus()

    # -----------------------------------------------------------------
    # Background scan worker
    # -----------------------------------------------------------------

    def _start_scan(self) -> None:
        """Launch the repository scan in a background worker thread."""
        self._scanning = True
        try:
            sidebar: RepoSidebar = self.query_one("#sidebar-container", RepoSidebar)
            sidebar.update_header(scanning=True)
        except Exception:
            pass
        self.run_worker(self._scan_worker, thread=True, exclusive=True, group="scan")

    def _scan_worker(self) -> list[RepoInfo]:
        """Worker function: scan filesystem and collect RepoInfo objects.

        Runs in a thread — no UI calls allowed here.
        Returns the sorted list of RepoInfo for the main thread to consume.
        """
        paths = scan_repos(self.root_dir)
        infos = [get_repo_info(p) for p in paths]
        infos.sort(key=lambda r: r.last_commit_ts, reverse=True)
        return infos

    def on_worker_state_changed(self, event: Worker.StateChanged) -> None:
        """Called on the main thread when the worker finishes."""
        if event.state == WorkerState.SUCCESS and event.worker.result is not None:
            self._scanning = False
            infos: list[RepoInfo] = event.worker.result
            self._all_repos = infos
            self.repos = list(infos)

            sidebar: RepoSidebar = self.query_one("#sidebar-container", RepoSidebar)
            sidebar.update_header(scanning=False, count=len(infos))
            sidebar.populate(self.repos)

            fleet: FleetStatus = self.query_one("#fleet-status", FleetStatus)
            fleet.update_counters(infos)

            if self.repos:
                self._select_repo(self.repos[0])

        elif event.state == WorkerState.ERROR:
            self._scanning = False
            self.notify(f"Scan failed: {event.worker.error}", severity="error", timeout=5)

    # -----------------------------------------------------------------
    # Internal helpers
    # -----------------------------------------------------------------

    def _select_repo(self, repo_info: RepoInfo) -> None:
        """Load a repo's data into the main panel."""
        self._selected_repo = repo_info
        # Update header subtitle to reflect the active repo + branch
        self.sub_title = f"{repo_info.name}  ·  {repo_info.branch}"
        main: MainPanel = self.query_one("#main-panel", MainPanel)
        main.load_repo(repo_info.path, repo_info)

    def _apply_filter(self, query: str) -> None:
        """Filter the repo list by name, re-populate sidebar."""
        q = query.strip().lower()
        if q:
            self.repos = [r for r in self._all_repos if q in r.name.lower()]
        else:
            self.repos = list(self._all_repos)

        sidebar: RepoSidebar = self.query_one("#sidebar-container", RepoSidebar)
        sidebar.populate(self.repos)
        if self.repos:
            self._select_repo(self.repos[0])

    def _apply_fleet_filter(self, category: str) -> None:
        """Filter sidebar to repos matching a fleet-status category."""
        from gitpulse.git_ops import RepoStatus  # avoid circular at module level
        _predicates = {
            "dirty":   lambda r: r.status != RepoStatus.CLEAN,
            "behind":  lambda r: r.behind > 0,
            "ahead":   lambda r: r.ahead > 0,
            "stashes": lambda r: r.stash_count > 0,
            "stale":   lambda r: r.has_stale_branches,
        }
        pred = _predicates.get(category)
        if pred is None:
            self.repos = list(self._all_repos)
        else:
            self.repos = [r for r in self._all_repos if pred(r)]

        sidebar: RepoSidebar = self.query_one("#sidebar-container", RepoSidebar)
        sidebar.populate(self.repos)

        if self.repos:
            self._select_repo(self.repos[0])

    # -----------------------------------------------------------------
    # Message handlers
    # -----------------------------------------------------------------

    def on_repo_sidebar_repo_selected(self, message: RepoSidebar.RepoSelected) -> None:
        """User navigated to a different repo in the sidebar."""
        self._select_repo(message.repo_info)

    def on_repo_sidebar_search_changed(self, message: RepoSidebar.SearchChanged) -> None:
        """User typed in the search bar."""
        self._apply_filter(message.query)

    def on_fleet_status_filter_requested(self, message: FleetStatus.FilterRequested) -> None:
        """User clicked a fleet chip — filter sidebar to matching repos."""
        self._apply_fleet_filter(message.category)

    def on_main_panel_branch_switch_requested(
        self, message: MainPanel.BranchSwitchRequested
    ) -> None:
        """User pressed Enter on a branch in the Branches tab."""
        if self._selected_repo is None:
            return

        result = switch_branch(self._selected_repo.path, message.branch_name)
        self.notify(result, timeout=3)

        # Refresh the selected repo's data
        updated_info = get_repo_info(self._selected_repo.path)
        self._select_repo(updated_info)

        # Also kick off a background rescan to update the sidebar
        self._start_scan()

    def on_main_panel_reload_requested(self, message: MainPanel.ReloadRequested) -> None:
        """Fired after a commit or branch operation — refresh sidebar entry."""
        if self._selected_repo is None:
            return
        updated_info = get_repo_info(self._selected_repo.path)
        self._selected_repo = updated_info
        # Rescan to update sidebar badges/timestamps
        self._start_scan()


# -----------------------------------------------------------------------
# CLI entry point
# -----------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        prog="gitpulse",
        description="GitPulse — Git Repo Dashboard TUI",
    )
    parser.add_argument(
        "--root",
        type=str,
        default=".",
        help="Root directory to scan for git repos (default: current directory)",
    )
    parser.add_argument(
        "--commits",
        type=int,
        default=10,
        metavar="N",
        help="Number of commits to display per repo (default: 10)",
    )
    parser.add_argument(
        "--config",
        type=str,
        default=None,
        metavar="PATH",
        help="Path to config.toml (default: ~/.config/gitpulse/config.toml)",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"gitpulse {__version__}",
    )
    return parser.parse_args()


def main() -> None:
    """Entry point — called by both `python main.py` and the `gitpulse` command."""
    args = parse_args()

    # Load config (custom path takes precedence)
    if args.config:
        _config.load(Path(args.config))

    root = Path(args.root).expanduser().resolve()

    if not root.is_dir():
        print(f"Error: '{root}' is not a valid directory.", file=sys.stderr)
        sys.exit(1)

    app = GitPulseApp(root_dir=root, commits=args.commits)
    app.run()


if __name__ == "__main__":
    main()
